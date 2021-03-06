#!/usr/bin/env python
from __future__ import division
"""
Path Marker Task, attempts to center on the path, orient itself and update next task's prior
Objectives:
- Search
- Follow
---> Center on the path marker
---> Orient with the path marker
---> Update next task's prior
"""
from tasks.task import Task, Objective
from tasks.search import Search
import numpy as np
import rospy
import smach
import smach_ros
from perception_control.msg import VisualServoAction, VisualServoGoal, VisualServoFeedback
from perception_control.msg import PathOrientAction, PathOrientGoal, PathOrientResult
import actionlib
from actuator.srv import ActivateActuator
from std_msgs.msg import Float64
from state_machine.srv import *
import tf

class Path(Task):
    name = "path"

    def __init__(self, path_num_str):
        self.name = "path" + path_num_str
        super(Path, self).__init__()
        self.init_objectives(path_num_str)
        self.link_objectives()

    def init_objectives(self, path_num_str):
        frame = "leviathan/description/downcam_frame_optical"
        self.search = Search.from_bounding_box(self.get_prior_param(), "path", frame)
        self.follow = Follow(path_num_str)

    def link_objectives(self):
        with self:
            smach.StateMachine.add('Search', self.search, transitions={'found':'Follow', 'not_found':'manager'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})
            smach.StateMachine.add('Follow', self.follow, transitions={'success':'manager', 'timed_out':'manager'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})

class Follow(Objective):
    """
    Center, orient, update next task's prior
    """
    outcomes=['success', 'timed_out']

    def __init__(self, path_num_str):
        self.path_num_str = path_num_str
        self.vs_client = actionlib.SimpleActionClient('visual_servo', VisualServoAction)
        rospy.loginfo("...waiting for visual_servo server")
        self.vs_client.wait_for_server()
        rospy.loginfo("\tfound visual servo server")
        self.centering_time = rospy.get_param("tasks/path"+path_num_str+"/centering_time")
        self.do_orientation = rospy.get_param("tasks/path"+path_num_str+"/do_orientation")
        if self.do_orientation:
            self.ori_client = actionlib.SimpleActionClient('path_orient', PathOrientAction)
            rospy.loginfo("...waiting for path_orient server")
            self.ori_client.wait_for_server()
            rospy.loginfo("\tfound path_orient server")
            self.orientation_result = None
        self.prior_adjustment_dist = rospy.get_param("tasks/path"+path_num_str+"/prior_adjustment_dist")
        if self.prior_adjustment_dist:
            rospy.loginfo("...waiting for get_next_task server")
            rospy.wait_for_service('cusub_cortex/state_machine/get_next_task')
            rospy.loginfo("\tfound get_next_task server")
        self.feedback = False
        self.was_centered = False
        # self.depth_pub = rospy.Publisher("cusub_common/motor_controllers/pid/depth/setpoint", Float64, queue_size=1)
        # self.depth_msg = Float64(); self.depth_msg.data = rospy.get_param("tasks/path"+path_num_str+"/depth")
        self.target_pixel_box = rospy.get_param("tasks/path"+path_num_str+"/target_pixel_threshold")
        
        super(Follow, self).__init__(self.outcomes, "Follow")

    def orientation_result_callback(self, state, result):
        self.orientation_result = result.oriented

    def vs_feedback_callback(self, feedback):
        self.feedback = feedback.centered

    def adjust_next_prior(self):
        quat = [self.cur_pose.orientation.x, self.cur_pose.orientation.y,self.cur_pose.orientation.z,self.cur_pose.orientation.w]
        roll, pitch, yaw = tf.transformations.euler_from_quaternion(quat)
        new_prior = []
        new_prior.append( float( self.cur_pose.position.x + self.prior_adjustment_dist * np.cos(yaw) ) )
        new_prior.append( float( self.cur_pose.position.y + self.prior_adjustment_dist * np.sin(yaw) ) )
        new_prior.append( self.cur_pose.position.z )
        get_next_task = rospy.ServiceProxy('cusub_cortex/state_machine/get_next_task', GetNextTask)
        res = get_next_task()
        if res.next_task != "mission_complete":
            rospy.loginfo("Updating next task's prior: %s", res.next_task)
            rospy.set_param("tasks/"+res.next_task+"/prior", new_prior)

    def execute(self, userdata):
        self.configure_darknet_cameras([0,0,0,0,0,1])
        goal = VisualServoGoal()
        goal.target_class = "path"
        goal.camera = goal.DOWNCAM
        goal.x_axis = goal.STRAFE_AXIS
        goal.y_axis = goal.DRIVE_AXIS
        goal.area_axis = goal.NO_AXIS
        goal.target_frame = rospy.get_param("~robotname") +"/description/downcam_frame_optical"
        goal.visual_servo_type = goal.PROPORTIONAL
        goal.target_pixel_x = goal.CAMERAS_CENTER_X
        goal.target_pixel_y = goal.CAMERAS_CENTER_Y
        goal.target_pixel_y = goal.CAMERAS_CENTER_Y
        goal.target_pixel_threshold = self.target_pixel_box
        rospy.loginfo("...centering over path marker")
        self.vs_client.send_goal(goal, feedback_cb=self.vs_feedback_callback)
        
        while not rospy.is_shutdown() :
            # self.depth_pub.publish(self.depth_msg)
            if userdata.timeout_obj.timed_out:
                self.vs_client.cancel_goal()
                userdata.outcome = "timed_out"
                return "timed_out"
            if self.feedback:
                if self.was_centered:
                    break
                else:
                    rospy.sleep(self.centering_time)
                    self.was_centered = True
            else:
                self.was_centered = False
            rospy.sleep(0.25)
        rospy.loginfo("\tcentered")

        if self.do_orientation:
            # call to orientation server
            ori_goal = PathOrientGoal()
            rospy.loginfo("...orienting with path marker")
            self.ori_client.send_goal(ori_goal, done_cb=self.orientation_result_callback)
            r = rospy.Rate(1)
            while not rospy.is_shutdown() and self.orientation_result == None:
                # self.depth_pub.publish(self.depth_msg)
                if userdata.timeout_obj.timed_out:
                    self.vs_client.cancel_goal()
                    self.ori_client.cancel_goal()
                    userdata.outcome = "timed_out"
                    return "timed_out"
                r.sleep()
            rospy.loginfo("\toriented")
        else:
            rospy.logwarn("...skipping orpientation")
        
        self.vs_client.cancel_goal()  # Tell VS to stop servoing

        if self.prior_adjustment_dist:
            self.adjust_next_prior()
        userdata.outcome = "success"
        return "success"