#ifndef AFFINETRANSFORM_H
#define AFFINETRANSFORM_H

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video.hpp>
#include "BoundingBox.h"

namespace perception_control
{

class AffineTransform
{
public:
    AffineTransform();
    AffineTransform(const AffineTransform &other);
    AffineTransform(const std::vector<cv::Point2f> &fromPts, const std::vector<cv::Point2f> &toPts);
    
    void transformPoints(std::vector<cv::Point2f> &pts);
    void transformBox(BoundingBox &box);

private:
    cv::Mat m_transform;

};

}; // namespace perception_control

#endif // AFFINETRANSFORM_H