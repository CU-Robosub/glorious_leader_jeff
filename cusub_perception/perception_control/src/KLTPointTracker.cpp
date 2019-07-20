#include "perception_control/KLTPointTracker.h"

using namespace perception_control;

#include <opencv2/highgui.hpp>
#include <opencv2/video.hpp>

KLTPointTracker::KLTPointTracker()
{}

PointTracker::Result KLTPointTracker::initialize(const cv::Mat &image, const BoundingBox &roi)
{
    cv::Mat imageCopy;
    cv::cvtColor(image, imageCopy, CV_BGR2GRAY);
    cv::Mat croppedImage = imageCopy(roi.roiRect());

    // extract shi-tomasi image features
    cv::goodFeaturesToTrack(croppedImage, m_currentPoints, 100, 0.3, 7, cv::Mat(), 7, false, 0.04);

    // shift back to full image
    for (cv::Point2f &pt : m_currentPoints)
    {
        pt.x += roi.xmin();
        pt.y += roi.ymin();
    }

    m_currentImg = imageCopy;

    return PointTracker::Result();
}

PointTracker::Result KLTPointTracker::trackPoints(const cv::Mat &image)
{
    cv::Mat imageGray;
    std::vector<cv::Point2f> newPoints, foundNewPoints;
    std::vector<uchar> pointStatus;
    std::vector<float> err;

    cv::cvtColor(image, imageGray, cv::COLOR_BGR2GRAY);
    cv::TermCriteria criteria = cv::TermCriteria((cv::TermCriteria::COUNT) + (cv::TermCriteria::EPS), 10, 0.03);

    cv::calcOpticalFlowPyrLK(m_currentImg, imageGray, m_currentPoints, newPoints, pointStatus, err, cv::Size(15,15), 2, criteria);

    for(uint i = 0; i < m_currentPoints.size(); i++)
    {
        // Select good points
        if(pointStatus[i] == 1)
        {
            foundNewPoints.push_back(newPoints[i]);
        }
    }
    
    AffineTransform transform = AffineTransform(m_currentPoints, foundNewPoints);

    // Now update the previous frame and previous points
    m_currentImg = imageGray.clone();
    m_currentPoints = foundNewPoints;

    PointTracker::STATUS status = PointTracker::STATUS::Success;
    std::string message = "Succeeded with " + std::to_string(foundNewPoints.size()) + " points";

    return PointTracker::Result(status, transform, message);
}

void KLTPointTracker::reset()
{

}