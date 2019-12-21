#ifndef DETECTION_TREE_NODE_SRC_DETECTION_TREE_NODE_H_
#define DETECTION_TREE_NODE_SRC_DETECTION_TREE_NODE_H_

#include <pluginlib/class_list_macros.h>
#include "detection_tree/detection_tree.hpp"
#include <nodelet/nodelet.h>
#include <ros/ros.h>
#include <vector>
#include <map>
#include <string>
#include <darknet_ros_msgs/BoundingBoxes.h>
#include <darknet_ros_msgs/BoundingBox.h>
#include <std_msgs/Header.h>
#include <geometry_msgs/PoseStamped.h>
#include <geometry_msgs/Quaternion.h>
#include <tf/transform_listener.h>
#include <tf/transform_datatypes.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#include <sensor_msgs/CameraInfo.h>
#include <cv_bridge/cv_bridge.h>
#include <sensor_msgs/image_encodings.h>
#include <opencv2/calib3d.hpp>
#include <detection_tree/Dvector.h>

// Camel case classes + functions, underscore variables + namespaces

namespace det_tree_ns
{
    class DetectionTree : public nodelet::Nodelet
    {
        public:
            virtual void onInit();
        private:
            std::string sub_name;
            void darknetCallback(const darknet_ros_msgs::BoundingBoxesConstPtr bbs);
            void cameraInfoCallback(const sensor_msgs::CameraInfo ci);
            detection_tree::Dvector* createDvector(darknet_ros_msgs::BoundingBox& bb, std_msgs::Header& image_header);
            bool boxToBearing(std_msgs::Header& camera_header, darknet_ros_msgs::BoundingBox& box, geometry_msgs::Quaternion& bearing);
            int determineDobject(detection_tree::Dvector* dv_ptr, Dobject* dobj_ptr); // -1 for new dobject
            void createDobject(detection_tree::Dvector* dv_ptr);
            void addDvectorToDobject(detection_tree::Dvector* dv_ptr, Dobject* dobj_ptr);
            bool poseSolveDobject(Dobject* dobj, geometry_msgs::Pose& pose);
            std::vector<Dobject> dobject_list;
            ros::Subscriber darknet_sub;
            ros::Publisher dvector_pub;
            ros::Publisher debug_pose_pub;
            tf::TransformListener listener;
            std::map<std::string, ros::Subscriber> camera_info_subs;
            std::map<std::string, sensor_msgs::CameraInfo> camera_info;
            std::map<std::string, std::string> camera_topic_frame_map = {
               {"/leviathan/cusub_common/occam/image0/camera_info", "leviathan/description/occam0_frame"},
               {"/leviathan/cusub_common/occam/image1/camera_info", "leviathan/description/occam1_frame"},
               {"/leviathan/cusub_common/occam/image2/camera_info", "leviathan/description/occam2_frame"},
               {"/leviathan/cusub_common/occam/image3/camera_info", "leviathan/description/occam3_frame"},
               {"/leviathan/cusub_common/occam/image4/camera_info", "leviathan/description/occam4_frame"},
               {"/leviathan/cusub_common/downcam/camera_info", "leviathan/description/downcam_frame"}
            }; // TODO move to launch file for configurability
            // std::map<std::string, std::string> camera_topic_frame_map = {
            //    {"/leviathan/cusub_common/occam/image0/camera_info", "leviathan/description/occam0_frame_optical"},
            //    {"/leviathan/cusub_common/occam/image1/camera_info", "leviathan/description/occam1_frame_optical"},
            //    {"/leviathan/cusub_common/occam/image2/camera_info", "leviathan/description/occam2_frame_optical"},
            //    {"/leviathan/cusub_common/occam/image3/camera_info", "leviathan/description/occam3_frame_optical"},
            //    {"/leviathan/cusub_common/occam/image4/camera_info", "leviathan/description/occam4_frame_optical"},
            //    {"/leviathan/cusub_common/downcam/camera_info", "leviathan/description/downcam_frame_optical"}
            // }; // TODO move to launch file for configurability
    };
}

#endif