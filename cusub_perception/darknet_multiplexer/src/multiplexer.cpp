/*
    Multiplexes occam and downcam camera frames into a single topic for darknet.
    Dynamically configurable via service TODO service name
    Update rate configurable via config/darknet_multiplexer.yaml
 */

 #include <darknet_multiplexer/multiplexer.h>

 namespace darknet_multiplexer_ns
 {
     void Multiplexer::onInit()
     {
         NODELET_INFO("Starting darknet multiplexer");
         nh = getMTNodeHandle();
         darknet_pub = nh.advertise<sensor_msgs::Image>("cusub_common/darknet_multiplexer/out", 1);
         actives_pub = nh.advertise<std_msgs::UInt8MultiArray>("cusub_common/darknet_multiplexer/actives", 1);
         int update_freq;

         if (!nh.getParam("darknet_multiplexer/update_freq", update_freq))
         {
             NODELET_ERROR("Darknet Multiplexer failed to locate params.");
             abort();
         }
         nh.getParam("darknet_multiplexer/startup_configuration", activeCameras);
         for(int i=0; i<image_received.size(); i++) { image_received[i]=false; }
         current_pub_index = 0;

         // Subscribe to all images
         subs.push_back( nh.subscribe("cusub_common/occam/image0", 1, &Multiplexer::occamCallback0, this) );
         subs.push_back( nh.subscribe("cusub_common/occam/image1", 1, &Multiplexer::occamCallback1, this) );
         subs.push_back( nh.subscribe("cusub_common/occam/image2", 1, &Multiplexer::occamCallback2, this) );
         subs.push_back( nh.subscribe("cusub_common/occam/image3", 1, &Multiplexer::occamCallback3, this) );
         subs.push_back( nh.subscribe("cusub_common/occam/image4", 1, &Multiplexer::occamCallback4, this) );
         subs.push_back( nh.subscribe("cusub_common/downcam", 1, &Multiplexer::downcamCallback, this) );

         NODELET_WARN("DM waiting for first image.");
         ros::topic::waitForMessage<sensor_msgs::Image>("cusub_common/occam/image0", nh);
         NODELET_INFO("Darknet Multiplexer received first image.");

         // Start configuration service
         service = nh.advertiseService("darknet_multiplexer/configure_active_cameras", &Multiplexer::configureActives, this);

         // Start update timer
         timer = nh.createTimer(ros::Duration(1 / (float) update_freq), &Multiplexer::publishFrame, this);
     }

    // Individual callbacks for speed, no logic about where to store images
     void Multiplexer::occamCallback0(const sensor_msgs::ImagePtr image) { recent_images[0] = image; image_received[0] = true; }
     void Multiplexer::occamCallback1(const sensor_msgs::ImagePtr image) { recent_images[1] = image; image_received[1] = true; }
     void Multiplexer::occamCallback2(const sensor_msgs::ImagePtr image) { recent_images[2] = image; image_received[2] = true; }
     void Multiplexer::occamCallback3(const sensor_msgs::ImagePtr image) { recent_images[3] = image; image_received[3] = true; }
     void Multiplexer::occamCallback4(const sensor_msgs::ImagePtr image) { recent_images[4] = image; image_received[4] = true; }
     void Multiplexer::downcamCallback(const sensor_msgs::ImagePtr image) { recent_images[5] = image; image_received[5] = true; }

     bool Multiplexer::configureActives(darknet_multiplexer::DarknetCameras::Request& request,
                                        darknet_multiplexer::DarknetCameras::Response& response)
                                        {
                                            if(request.actives.size() == activeCameras.size())
                                            {
                                                for(int i=0; i<activeCameras.size();i++) { activeCameras[i] = request.actives[i]; }
                                                response.success = true;
                                                return true;
                                            } else { 
                                                response.success = false; 
                                                return false;
                                            }
                                        }

     void Multiplexer::publishFrame(const ros::TimerEvent& event)
     {
         bool frame_published = false;
         while( !frame_published && ros::ok())
         {
            if( activeCameras[current_pub_index] && image_received[current_pub_index] )
            {
                darknet_pub.publish(recent_images[current_pub_index]);
                frame_published = true;
            }
            current_pub_index = (current_pub_index + 1) % activeCameras.size();
         }
         std_msgs::UInt8MultiArray msg;
         for(int i=0;i<activeCameras.size();i++) { msg.data.push_back(activeCameras[i]); }
         actives_pub.publish(msg);
     }
 }

 PLUGINLIB_EXPORT_CLASS(darknet_multiplexer_ns::Multiplexer, nodelet::Nodelet);