#!/usr/bin/env python
from __future__ import division

import rospy

from sensor_msgs.msg import Image
from darknet_ros_msgs.msg import BoundingBox, BoundingBoxes

from localizer.srv import ClassicalBoxes2Poses

from geometry_msgs.msg import Pose

from cv_bridge import CvBridge, CvBridgeError

import numpy as np
import cv2

class RouletteWatershedServer():

    # 2-3
    # | |
    # 1 4
    roulette_truth_points = np.array([[-0.22, -0.36, 0],
                                      [-0.22,  0.36, 0],
                                      [ 0.22,  0.36, 0],
                                      [ 0.22, -0.36,  0]], dtype=np.float32)

    downcam_camera_matrix = np.array([344.133456, 0.000000, 663.520917, 0.000000, 344.629709, 478.643504, 0.000000, 0.000000, 1.000000])
    downcam_distortion_coefs = np.array([0.035690, -0.010044, 0.000537, -0.000878, 0.000000])

    
    def __init__(self):

        ns = rospy.get_namespace()

        self.server = rospy.Service(ns+"cusub_perception/localize_roulette_watershed", ClassicalBoxes2Poses, self.localize)
        self.downcam_camera_matrix.shape = (3,3)

        # print(self.roulette_truth_points)

        rospy.loginfo("Roulette Watershed Initialized")

        self.bridge = CvBridge()

    def localize(self, req):

        img = self.bridge.imgmsg_to_cv2(req.image, "passthrough")
        #debug_img = img.copy()

        # Fill Background
        markers = np.ones((req.image.height, req.image.width), dtype=np.int32)

        marker_count = 2
        poses = []
        classes = []
        for box in req.boxes:

            if box.Class != "roulette":
                continue

            box_margin = 20

            # Clear Bounding Box
            markers[box.ymin-box_margin:box.ymax+box_margin, box.xmin-box_margin:box.xmax+box_margin] = 0
            #cv2.rectangle(debug_img, (box.xmin-box_margin, box.ymin-box_margin), (box.xmax+box_margin, box.ymax+box_margin), (0,255,0), 3)

            # Add marker
            box_width = box.xmax - box.xmin
            box_height = box.ymax - box.ymin
            box_x_center = int(box.xmin + box_width / 2.0)
            box_y_center = int(box.ymin + box_height / 2.0)
            marker_width = 0.25
            m_xmin = int(box_x_center - box_width * marker_width / 2.0)
            m_xmax = int(box_x_center + box_width * marker_width / 2.0)
            m_ymin = int(box_y_center - box_height * marker_width / 2.0)
            m_ymax = int(box_y_center + box_height * marker_width / 2.0)
            markers[m_ymin:m_ymax, m_xmin:m_xmax] = marker_count
            #cv2.rectangle(debug_img, (m_xmin, m_ymin), (m_xmax, m_ymax), (0,0,255), 3)

            marker_count += 1

        if marker_count == 2: # noting found
            return None, None

        cv2.watershed(img, markers)

        marker_pos = np.argwhere(markers == 2)

        marker_xmin_idx = np.argmin(marker_pos[:,0])
        marker_xmin_x = marker_pos[marker_xmin_idx,0]
        marker_xmin_y = marker_pos[marker_xmin_idx,1]
        marker_left = (marker_xmin_y, marker_xmin_x)

        marker_xmax_idx = np.argmax(marker_pos[:,0])
        marker_xmax_x = marker_pos[marker_xmax_idx,0]
        marker_xmax_y = marker_pos[marker_xmax_idx,1]
        marker_right = (marker_xmax_y, marker_xmax_x)

        marker_ymin_idx = np.argmin(marker_pos[:,1])
        marker_ymin_x = marker_pos[marker_ymin_idx,0]
        marker_ymin_y = marker_pos[marker_ymin_idx,1]
        marker_top = (marker_ymin_y, marker_ymin_x)

        marker_ymax_idx = np.argmax(marker_pos[:,1])
        marker_ymax_x = marker_pos[marker_ymax_idx,0]
        marker_ymax_y = marker_pos[marker_ymax_idx,1]
        marker_bottom = (marker_ymax_y, marker_ymax_x)

        l1 = np.linalg.norm(np.array(marker_left)  - np.array(marker_top))
        l2 = np.linalg.norm(np.array(marker_right) - np.array(marker_top))

        # print(l1, l2)

        # print(marker_left, marker_right, marker_top, marker_bottom)

        # 2-3
        # | |
        # 1 4
        pr_arr = None
        if(l2 > l1):
            # top to right is long side
            pt_arr = np.array([marker_bottom, marker_left, marker_top, marker_right], dtype=np.float32)
        else:
            # top to left is long side
            pt_arr = np.array([marker_left, marker_top, marker_right, marker_bottom], dtype=np.float32)

        retval, rvec, tvec = cv2.solvePnP(self.roulette_truth_points, pt_arr, self.downcam_camera_matrix, self.downcam_distortion_coefs)

        # # PnP uses different coord system, do quick conversion
        pose = Pose()
        pose.position.x = tvec[0]
        pose.position.y = tvec[1]
        pose.position.z = tvec[2]

        poses.append(pose)

        # print(pose)

        box = req.boxes[0]
        classes.append(box.Class)
        rospy.loginfo(box.Class + " : " + str(pose))

        """
        res = cv2.convertScaleAbs(markers)
        _, res = cv2.threshold(res,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        cv2.imshow('image', res)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        """

        # cv2.imshow('image', markers)

        """
        cv2.circle(debug_img, marker_left, 5, (0,0,255), -1)
        cv2.circle(debug_img, marker_right, 5, (0,0,255), -1)
        cv2.circle(debug_img, marker_bottom, 5, (0,0,255), -1)
        cv2.circle(debug_img, marker_top, 5, (0,0,255), -1)

        cv2.imshow('image', debug_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        """

        return poses, classes

def main():
    rospy.init_node('roulette_watershed')
    server = RouletteWatershedServer()
    rospy.spin()

class PsudoRequest():
    image = None
    boxes = []
    def __init__(self):
        pass

def test1():
    server = RouletteWatershedServer()

    bridge = CvBridge()
    cv_image = cv2.imread('test.jpg', 3)
    image_message = bridge.cv2_to_imgmsg(cv_image, "passthrough")

    roulette_box = BoundingBox()
    roulette_box.xmin = 793
    roulette_box.ymin = 415
    roulette_box.xmax = 1000
    roulette_box.ymax = 600
    
    req = PsudoRequest()
    req.image = image_message
    req.boxes.append(roulette_box)

    server.localize(req)

if __name__ == "__main__":
    # test1()
    main()