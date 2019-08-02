#!/usr/bin/env python
from __future__ import division
"""
Startup Task
"""
import rospy
import smach
import smach_ros
import rospy
from std_msgs.msg import Float64
from tasks.task import Task, Objective

class Startup(Task):
    name = "startup"

    def __init__(self):
        super(Startup, self).__init__() # become a state machine first
        self.init_objectives()
        self.link_objectives()

    def init_objectives(self):
        self.dive = Dive()

    def link_objectives(self):
        with self: # we are a StateMachine
            smach.StateMachine.add('Dive', self.dive, transitions={'done':'manager'}, \
                remapping={'timeout_obj':'timeout_obj', 'outcome':'outcome'})

class Dive(Objective):

    outcomes=['done']

    def __init__(self):
        super(Dive, self).__init__(self.outcomes, "Dive")
        self.dive_pub = rospy.Publisher("cusub_common/motor_controllers/pid/depth/setpoint", Float64, queue_size=1)

    def execute(self, userdata):
        depth_msg = Float64()
        depth_msg.data = rospy.get_param("tasks/startup/depth")
        rospy.loginfo("...diving")
        while not rospy.is_shutdown():
            self.dive_pub.publish(depth_msg)
            if userdata.timeout_obj.timed_out:
                break
            rospy.sleep(0.25)
        userdata.outcome = "success"
        return "done"