#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from __future__ import division
"""
Droppers Task, attempts to drop 2 markers in the bin
Objectives:
- Search
- Approach
"""
from tasks.task import Task, Objective, Timeout
from tasks.search import Search
from tasks.pid_client import PIDClient
import rospy
import smach
import smach_ros
from detection_listener.listener import DetectionListener
import numpy as np
from tf.transformations import euler_from_quaternion
from geometry_msgs.msg import PoseStamped, Pose
from localizer_msgs.msg import Detection
from actuator.srv import ActivateActuator
from cusub_print.cuprint import bcolors

class Droppers(Task):
    name = "Droppers"

    def __init__(self):
        super(Droppers, self).__init__(self.name)

        # All Objectives share the same listener to gaurantee same data between objectives
        self.listener = DetectionListener() 

        self.init_objectives()
        self.link_objectives()

    def init_objectives(self):
        drive_client = PIDClient(self.name, "drive")
        strafe_client = PIDClient(self.name, "strafe")
        clients = {'drive_client' : drive_client, 'strafe_client' : strafe_client}
        search_classes = ["dropper_cover", "wolf"]
        darknet_cameras = [0,0,0,0,0,1] # front 3 occams + downcam
        self.search = Search(self.name, self.listener, search_classes, self.get_prior_param(), darknet_cameras=darknet_cameras)
        self.approach = Approach(self.name, self.listener, clients)
        self.drop = Drop(self.name, self.listener, clients)
        self.retrace = Retrace(self.name, self.listener)                

    def link_objectives(self):
        with self:
            smach.StateMachine.add('Search', self.search, transitions={'found':'Approach', 'not_found':'manager'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})
            smach.StateMachine.add('Retrace', self.retrace, transitions={'found':'Approach', 'not_found':'Search'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})
            smach.StateMachine.add('Approach', self.approach, transitions={'in_position':'Drop', 'timed_out':'manager', 'lost_object':'Retrace'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})
            smach.StateMachine.add('Drop', self.drop, transitions={'dropped':'manager', 'timed_out':'manager', 'lost_object':'Retrace'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})
            

class Approach(Objective):
    outcomes = ['in_position','timed_out', 'lost_object']
    
    target_class_ids = ["dropper_cover", "wolf"]

    def __init__(self, task_name, listener, clients):
        name = task_name + "/Approach"
        super(Approach, self).__init__(self.outcomes, name)
        self.drive_client = clients["drive_client"]
        self.strafe_client = clients["strafe_client"]
        self.listener = listener

        # approach via any target class id
        # focus on the priority id onoce we detect it.
        self.priority_id_flag = False
        self.priority_class_id = "wolf"

        self.xy_distance_thresh = rospy.get_param("tasks/droppers/xy_dist_thresh_app")

        self.retrace_timeout = rospy.get_param("tasks/" + task_name.lower() + "/retrace_timeout", 2)
        seconds = rospy.get_param("tasks/droppers/seconds_in_position")
        self.rate = 30
        self.count_target = seconds * self.rate
        self.count = 0

        self.dropper_pose = None
        self.new_pose_flag = False
        # rospy.Subscriber("cusub_cortex/mapper_out/start_gate", PoseStamped, self.dropper_pose_callback) # mapper
        rospy.Subscriber("cusub_perception/mapper/task_poses", Detection, self.dropper_pose_callback)
        
    def execute(self, userdata):
        self.cuprint("executing")
        self.configure_darknet_cameras([0,0,0,0,0,1])
        self.toggle_waypoint_control(True)

        # Find dropper_cover's dobject number and check for errors
        dobj_dict = self.listener.query_classes(self.target_class_ids)
        if not dobj_dict: # Check if target class is not present (shouldn't be possible)
            self.cuprint("somehow no " + str(self.target_class_ids) + " classes found in listener?", warn=True)
            return "lost_object"
        print_str = "dobj nums found: "
        for class_ in dobj_dict:
            print_str += bcolors.HEADER + bcolors.BOLD + class_ + ": " + bcolors.ENDC + str(dobj_dict[class_][0]) + bcolors.ENDC + "; "
        self.cuprint(print_str)

        watchdog_timer = Timeout(self.name + u"/Rétrace Watchdog".encode("utf-8"))

        # Check we've got a pose, if not return to lost_object which will return to pose of the detection
        if self.dropper_pose == None:
            rospy.sleep(2) # Wait for the pose to be sent by localizer
            if self.dropper_pose == None:
                self.cuprint("Dropper Pose still not received. ", warn=True)
                self.priority_id_flag = False
                return "lost_object"

        self.drive_client.enable()
        self.strafe_client.enable()

        drive, strafe = self.get_relative_drive_strafe(self.dropper_pose)
        self.clear_new_pose_flag()
        drive_setpoint = self.drive_client.get_standard_state() + drive
        strafe_setpoint = self.strafe_client.get_standard_state() + strafe
        self.drive_client.set_setpoint(drive_setpoint)
        self.strafe_client.set_setpoint(strafe_setpoint)
        watchdog_timer.set_new_time(self.retrace_timeout, print_new_time=False)

        self.cuprint("servoing")
        printed = False
        r = rospy.Rate(self.rate)
        print("") # overwritten by servoing status
        while not rospy.is_shutdown():
            if self.check_new_pose():
                watchdog_timer.set_new_time(self.retrace_timeout, print_new_time=False)
                self.clear_new_pose_flag()
                drive, strafe = self.get_relative_drive_strafe(self.dropper_pose)
                drive_setpoint = self.drive_client.get_standard_state() + drive
                strafe_setpoint = self.strafe_client.get_standard_state() + strafe

                if self.check_in_position():
                    self.count += 1
                    if self.count > self.count_target and not printed:
                        printed = True
                        break
                else:
                    self.count = 0
                    printed = False

            elif watchdog_timer.timed_out:
                self.drive_client.disable()
                self.strafe_client.disable()
                self.cuprint("Retrace watchdog timed out. :(", warn=True)
                self.priority_id_flag = False
                return "lost_object"

            if userdata.timeout_obj.timed_out:
                watchdog_timer.timer.shutdown()
                userdata.outcome = "timed_out"
                return "not_found"

            self.drive_client.set_setpoint(drive_setpoint, loop=False)
            self.strafe_client.set_setpoint(strafe_setpoint, loop=False)
            r.sleep()
        watchdog_timer.timer.shutdown()
        return "in_position"

    def get_relative_drive_strafe(self, dropper_pose):
        """
        Gets the relative drive, strafe changes to reach the dropper pose
        """
        ori = self.cur_pose.orientation
        sub_rol, sub_pitch, sub_yaw = euler_from_quaternion([ori.x, ori.y, ori.z, ori.w])

        x_diff = dropper_pose.position.x - self.cur_pose.position.x
        y_diff = dropper_pose.position.y - self.cur_pose.position.y

        # Numerical stability
        if abs(x_diff) < 0.0001:
            x_diff = 0.0001 * np.sign(x_diff)
        if abs(y_diff) < 0.0001:
            y_diff = 0.0001 * np.sign(y_diff)

        dist_to_dropper = np.linalg.norm([x_diff, y_diff])
        relative_yaw_diff = np.arctan2(y_diff, x_diff) - sub_yaw
        drive = dist_to_dropper * np.cos(relative_yaw_diff)
        strafe = - dist_to_dropper * np.sin(relative_yaw_diff) # flip strafe

        return [drive, strafe]

    def check_in_position(self): 
        x_diff = round( self.dropper_pose.position.x - self.cur_pose.position.x, 2)
        y_diff = round( self.dropper_pose.position.y - self.cur_pose.position.y, 2)
        x_str = "{:.2f}".format(x_diff)
        y_str = "{:.2f}".format(y_diff)
        self.cuprint("Error x: " + bcolors.HEADER + x_str + bcolors.ENDC + " | y: " + bcolors.HEADER + y_str + bcolors.ENDC, print_prev_line=True)
        return np.linalg.norm([x_diff, y_diff]) < self.xy_distance_thresh

    def dropper_pose_callback(self, msg):
        if msg.class_id in self.target_class_ids and not self.priority_id_flag:
            if msg.class_id == self.priority_class_id:
                self.priority_id_flag = True
            self.dropper_pose = msg.pose.pose
            self.new_pose_flag = True
        elif self.priority_id_flag:
            if msg.class_id == self.priority_class_id:
                self.dropper_pose = msg.pose.pose
                self.new_pose_flag = True

    def clear_new_pose_flag(self):
        self.new_pose_flag = False
    def check_new_pose(self):
        return self.new_pose_flag

class Drop(Approach): # share that code again...
    outcomes = ['dropped','timed_out', 'lost_object']

    target_class = "wolf"
    
    def __init__(self, task_name, listener, clients):
        name = task_name + "/Drop"
        super(Approach, self).__init__(self.outcomes, name)
        self.drive_client = clients["drive_client"]
        self.strafe_client = clients["strafe_client"]
        self.depth_client = PIDClient(name, "depth")

        self.xy_distance_thresh = rospy.get_param("tasks/droppers/xy_dist_thresh_drop")
        self.drop_depth = rospy.get_param("tasks/droppers/drop_depth")

        self.listener = listener
        self.retrace_timeout = rospy.get_param("tasks/droppers/retrace_timeout")

        self.rate = 30
        self.count_target = 0 # 0 since once we're in position, drop
        self.count = 0

        self.dropper_pose = None
        self.new_pose_flag = False
        # rospy.Subscriber("cusub_cortex/mapper_out/start_gate", PoseStamped, self.dropper_pose_callback) # mapper
        rospy.Subscriber("cusub_perception/mapper/task_poses", Detection, self.dropper_pose_callback)

        self.cuprint("waiting for actuator service")
        rospy.wait_for_service("cusub_common/activateActuator")
        self.cuprint("...connected")
        self.actuator_service = rospy.ServiceProxy("cusub_common/activateActuator", ActivateActuator)

    def execute(self, userdata):
        self.cuprint("diving")
        self.depth_client.set_setpoint(self.drop_depth)
        rospy.sleep(1.5)

        ret = super(Drop, self).execute(userdata)
        if ret == "in_position":
            self.cuprint("Bombs Away")
            self.actuate_dropper(1)
            # self.actuate_dropper(2)
            return "dropped"
        else:
            return ret

    def actuate_dropper(self, dropper_num):
        self.actuator_service(dropper_num, 500)

    def dropper_pose_callback(self, msg):
        if msg.class_id == self.target_class:
            self.dropper_pose = msg.pose.pose
            self.new_pose_flag = True

        
class Retrace(Objective):
    outcomes = ['found','not_found']

    target_class_ids = ["dropper_cover", "wolf"]


    def __init__(self, task_name, listener):
        super(Retrace, self).__init__(self.outcomes, task_name + "/Retrace")
        self.listener = listener
        #TODO: add param
        self.retrace_hit_cnt = rospy.get_param("tasks/" + task_name.lower() + "/retrace_hit_count")

    #TODO: Analyze assumption made: take most recent dvector from each target_class?
    # Or, go through each one in every dvector list?
    def find_nearest_breadcrumb(self, d_vectors):
        min_dis = float("Inf")
        index = 0
        for i in range(len(d_vectors)):
            new_dis = self.get_distance(self.cur_pose.position, d_vectors[i].sub_pt)
            if new_dis < min_dis:
                min_dis = new_dis
                index = i
        return index

    def execute(self, userdata):
        self.configure_darknet_cameras([1,1,1,1,1,1])
        self.toggle_waypoint_control(False)
        self.cuprint(u"executing Rétrace".encode("utf-8"))
        dobj_dict = self.listener.query_classes(self.target_class_ids)
        # For droppers, there should only be 3 Dobjects: droppers, wolf, bat.
        # So now I want to extract these Dobjects from the dobj_dict,
        # while hopefully adding some false positive rejection...
        self.cuprint(str(dobj_dict))
        dobj_nums = []
        for target in self.target_class_ids:
            nums = dobj_dict[target]
            if len(nums) > 1:
                # shouldn't have multiple dobjects, choose the one with most dvectors
                max_num = max([len(self.listener.dobjects[i].dvectors) for i in nums])
                dobj_nums.append(self.listener.dobjects.index(max_num))
            else:
                dobj_nums.append(nums[0])

        #now, dobj_nums has the object index for each of the three Dobjects, if they exist    

        #make sure we clear any preexisting flags.
        self.listener.clear_new_dv_flags(dobj_nums)

        #loop variables
        count = 0
        retraced_steps = [1 for i in self.target_class_ids]
        len_dvecs = [len(self.listener[id].dvectors) for id in dobj_nums]
        for i in range(len(self.target_class_ids)):
            string = "Total dvectors found for " + bcolors.HEADER + bcolors.BOLD + self.target_class_ids[i] + bcolors.ENDC
            self.cuprint(string + ": " + bcolors.OKBLUE + str(len_dvecs[i]) + bcolors.ENDC)
        recent_dvectors = [self.listener[dobj_nums[id]][len_dvecs[id]-retraced_steps[id]] for id in range(len(self.target_class_ids))]
        nearest_breadcrumb_id = self.find_nearest_breadcrumb(recent_dvectors)
        last_sub_pt = recent_dvectors[nearest_breadcrumb_id].sub_pt
        last_pose = Pose(last_sub_pt, self.cur_pose.orientation)

        #Start Retrace: Set first waypoint
        self.go_to_pose_non_blocking(last_pose, move_mode="strafe")
        # necessary for same-line printing
        print("")
        while not rospy.is_shutdown():
            if self.listener.check_new_dvs(dobj_nums) != None and count < self.retrace_hit_cnt: 

                #found object again
                count += 1
                if count >= self.retrace_hit_cnt:
                    self.cancel_way_client_goal()
                    return "found"
            else:  
                cur_id = self.target_class_ids[nearest_breadcrumb_id]
                cur_num = retraced_steps[nearest_breadcrumb_id]
                dist = round(self.get_distance(self.cur_pose.position, last_pose.position),3)
                self.cuprint("BC_ID " + bcolors.HEADER + cur_id + " # " + str(cur_num)+ bcolors.ENDC + " dist: " + bcolors.OKBLUE + str(dist) + bcolors.ENDC, print_prev_line=True)
                if self.check_reached_pose(last_pose):
                    retraced_steps[nearest_breadcrumb_id] += 1
                    if (retraced_steps[nearest_breadcrumb_id] > len_dvecs[nearest_breadcrumb_id]):
                        self.target_class_ids.pop(nearest_breadcrumb_id)     # class list is local to this state so pop() is ok?
                        if len(self.target_class_ids) == 0:
                            #means we retraces all our steps. We're lost.
                            return "not_found"
                    # Goto Last dvector
                    # get last dvector sub_pt
                    recent_dvectors = [self.listener[dobj_nums[id]][len_dvecs[id]-retraced_steps[id]] for id in range(len(self.target_class_ids))]
                    nearest_breadcrumb_id = self.find_nearest_breadcrumb(recent_dvectors)
                    last_sub_pt = recent_dvectors[nearest_breadcrumb_id].sub_pt
                    last_pose = Pose(last_sub_pt, self.cur_pose.orientation)
            
                    #set waypoint to this point. Give some distance to account for error in bearing and sub_pt
                    # Set waypoint
                    self.go_to_pose_non_blocking(last_pose, move_mode="strafe",log_print=False)

            if userdata.timeout_obj.timed_out:
                self.cancel_way_client_goal()
                userdata.outcome = "timed_out"
                return "not_found"
            rospy.sleep(.5)

        #clean up if we are killed
        return "not_found"