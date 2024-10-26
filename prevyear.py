# -*- coding: utf-8 -*-
"""PrevYear.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1z1aNgXJdnSe9BcmA-IZ_DEzGLYFSg0pd
"""



import Serial
import rospy
from std_msgs.msg import Float64MultiArray, Float64, Bool, Int32MultiArray
from math import *
from util import *
from time import sleep

rospy.init_node('qualification', anonymous=True)


# The distance needed to move through the gate after the flag are out of sight in m
through_gate = 2
# Width of the gate in m
gate_width = 3
# Move step size
step = 0.2
# Contain the class number for each object
cvDict = {"pole":0}

# CV_result: A list of bounding boxes [x1, x2, y1, y2, class]. (x1, y1) is the top left corner. (x2, y2) is the bottom right corner. Coordinates from 0-1
# angle: The angles on x-axis, y-axis, and z-axis from gyrometer. Format is 360 degrees. angles[2] is suppose to be the horizontal angle
# depth: The distance from the bottom of the pool in meters
# pressure: The distance from water surface in meters.
sensor={}

# Subscribe to the CV output
cvSub = rospy.Subscriber('CV', Float64MultiArray, cvCallback, callback_args=sensor)
cvBottomSUb = rospy.Subscriber('CVbottom', Float64MultiArray, cvBottomCallback, callback_args=sensor)

thrusterPub = rospy.Publisher("thruster", Int32MultiArray)
# Get distance from bottom from bottom camera
depthSub = rospy.Subscriber('depth_sensor', Float64, depthCallback, callback_args=sensor)
# Get angle from IMU
gyroSub = rospy.Subscriber('gyro_sensor', Float64MultiArray, gyroCallback, callback_args=sensor)
# From touch sensor
touchSub = rospy.Subscriber("touch_sensor", Bool, touchCallback, callback_args=sensor)
# Get distance from surface from pressure sensor
pressureSub = rospy.Subscriber("pressure_sensor", Float64, pressureCallback, callback_args=sensor)
# Get distance travelled from IMU
distanceSub = rospy.Subscriber("displacement_sensor", Float64MultiArray, distanceCallback, callback_args=sensor)

def alignPath(path):
  # First place the path at the center of the image.
  # Then use the width of the bounding box to determine the direction of the path.
  # path is the initial bounding box of the path.
  x_center = (path[0] + path[1])/2
  yCenter = (path[2] + path[3])/2
  while abs(x_center - 0.5) > 0.05 or abs(yCenter - 0.5) > 0.05:
    if abs(yCenter - 0.5) > 0.05:
      # y-coordinate is not aligned
      if yCenter > 0.5:
        # If path is at the upper part of the frame, move forward.
        move("forward", sensor, thrusterPub, 0.1)
        bboxes = cvBottom()
        path = findObject("path", sensor, cvDict)
        while(not path):
          # Path is no longer in the frame, which means we overshoot
          move("backward", sensor, thrusterPub, 0.01)
          bboxes = cvBottom()
          path = findObject("path")
      else:
        # Path is at the lower part of the frame, move backward.
        move("backward", sensor, thrusterPub, 0.1)
        bboxes = cvBottom(sensor)
        path = findObject("path")
        while(not path):
          move("forward", sensor, thrusterPub, 0.01)
          bboxes = cvBottom(sensor)
          path = findObject("path")
    else:
      if x_center > 0.5:
        # If path is at the upper part of the frame, move forward.
        turn(90, sensor, thrusterPub)
        move("forward", sensor, thrusterPub, 0.1)
        turn(270, sensor, thrusterPub)
        bboxes = cvBottom(sensor)
        path = findObject("path")
        while(not path):
          turn(270, sensor, thrusterPub)
          move("forward", sensor, thrusterPub, 0.01)
          turn(90, sensor, thrusterPub)
          bboxes = cvBottom(sensor)
          path = findObject("path")
      else:
        turn(270, sensor, thrusterPub)
        move("forward", sensor, thrusterPub, 0.1)
        turn(90, sensor, thrusterPub)
        bboxes = cvBottom(sensor)
        path = findObject("path")
        while(not path):
          turn(90, sensor, thrusterPub)
          move("forward", sensor, thrusterPub, 0.01)
          turn(270, sensor, thrusterPub)
          bboxes = cvBottom(sensor)
          path = findObject("path")
      x_center = (path[0] + path[1])/2
      yCenter = (path[2] + path[3])/2
    directPath(path)


def directPath(pathObj):
  # Use the width of the bounding box to determine the direction of the path.
  # At the start of the function, we are pointing away from the gate
  width = pathObj[1] - pathObj[0]
  length = pathObj[3] - pathObj[2]
  cur_ratio = length/width
  turning_angle = 0
  #cur_ratio is the largest ratio


  for i in range(0,90,5):
    turn(5, sensor, thrusterPub)
    # Get the current bounding box ratio
    pathObj = cvBottom(sensor)
    width = pathObj[1] - pathObj[0]
    length = pathObj[3] - pathObj[2]
    new_ratio = length/width
    if new_ratio>cur_ratio:
      cur_ratio = new_ratio
      turning_angle = i
  turn(180, sensor, thrusterPub)

  for i in range(0,90,5):
    turn(5, sensor, thrusterPub)
    # Get the current bounding box ratio
    width = pathObj[1] - pathObj[0]
    length = pathObj[3] - pathObj[2]
    new_ratio = length/width
    if new_ratio>cur_ratio:
      cur_ratio = new_ratio
      turning_angle = i+270
  #turning_angle with the largest ratio
  turn(turning_angle, sensor, thrusterPub)
  #robot facing the direction of the path marker

def followThePath():
  # Find the path and then orient the robot in the direction of the path
  changeDepth(1.5, sensor, thrusterPub)
  while True:
    turn(270, sensor, thrusterPub)
    # Move left from the point out of the gate for the gate's width while search for the gate
    for i in range(ceil(gate_width / step)):
      bboxes = cvBottom(sensor)
      path = findObject("path")
      if path:
        # If path is found, turn to point away from the gate and align the gate.
        turn (90)
        alignPath(path)
        return
    turn(180, sensor, thrusterPub)
    # Turn 180 degrees, move right from the point out of the gate for double the gate's width while search for the gate
    # This is to cover the distance we moved left
    for i in range(ceil((gate_width * 2) / step)):
      bboxes = cvBottom(sensor)
      path = findObject("path")
      if path:
        turn(270, sensor, thrusterPub)
        # If path is found, turn to point away from the gate and align the gate.
        alignPath(path)
        return
    move("backward", sensor, thrusterPub, gate_width * 2)
    turn(270, sensor, thrusterPub)
    move("forward", sensor, thrusterPub, 1)

def alignVertical(obj):
  # Align the obj vertically.
  reachedBottom = False
  while (True):
    found = False
    for i in cv(sensor):
      # Detected the obj
      if i[4] == cvDict[obj]:
        y1 = i[2]
        y2 = i[3]
        yCenter = (y1+y2)/2
        found = True
        if abs(yCenter - 0.5) > 0.05:
          if yCenter > 0.5:
            move("up", sensor, thrusterPub)
          else:
            move("down", sensor, thrusterPub)
        else:
          return True

    if not found:
      # obj not detected by cv
      if sensor.get("depth") > 0.2 and not reachedBottom:
        # Have not reached bottom of pool before, so search by going down.
        move("down", sensor, thrusterPub)
      elif sensor.get("pressure") > 0.3:
        # Have reached bottom of pool, so search by going up.
        reachedBottom = True
        move("up", sensor, thrusterPub)
      else:
        # Reached top and bottom, object not found 
        print("Cannot find object")
        return False

def buoy(classNum):
  # Hit the object corresponding to classNum on the buoy
  # classNum is a string indicating the class to hit.

  # Change the depth to the depth of the buoy.
  changeDepth(0.9, sensor, thrusterPub)
  # Move until buoy is within sight.
  while not findObject("buoy"):
    move("forward", sensor, thrusterPub)
  # Align buoy to the center of the frame both horizontally and vertically.
  alignVertical("buoy")
  alignObj("buoy", sensor, thrusterPub, cvDict)
  # Move until one of the two images of the correct class is within frame.
  while not findObject(classNum+"img2") and not findObject(classNum+"img2"):
    move("forward", sensor, thrusterPub)
  # Assign one image of the correct class that is within the frame to be targetObj.
  targetObj = None
  if findObject(classNum+"img2"):
    targetObj = classNum+"img2"
  else:
    targetObj = classNum+"img3"
  # Align targetObj to the center of the frame both horizontally and vertically.
  alignVertical(targetObj)
  alignObj(targetObj, sensor, thrusterPub, cvDict)
  # Move forward until the buoy is hit.
  while not sensor.get("touch"):
    move("forward", sensor, thrusterPub)



def main():
  while True:
    if sensor.get("touch"):
      sleep(60)
      break
  changeDepth(0.3, sensor, thrusterPub)
  searchGate("left", sensor, thrusterPub, cvDict)
  targetClass = None # The string for which class we are targeting.
  while not findObject("class1img1") and not findObject("class2img1"):
    move("forward", sensor, thrusterPub)
  if findObject("class1img1"):
    targetClass = "class1"
    alignObj("class1img1")
  else:
    targetClass = "class2"
    alignObj("class2img1")
  moveTillGone(targetClass+"img1", sensor, thrusterPub)
  for i in range(ceil(through_gate/step)):
    move("forward", sensor, thrusterPub)
  followThePath()
  buoy(targetClass)
  changeDepth(0, sensor, thrusterPub)