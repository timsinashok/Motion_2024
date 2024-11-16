# -*- coding: utf-8 -*-
"""PrevYear.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1z1aNgXJdnSe9BcmA-IZ_DEzGLYFSg0pd
"""


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
cvBottomSUb = rospy.Subscriber('CV_bottom', Float64MultiArray, cvBottomCallback, callback_args=sensor)

thrusterPub = rospy.Publisher("thruster", Int32MultiArray)
# Get distance from bottom from bottom camera
depthSub = rospy.Subscriber('depth_sensor', Float64, depthCallback, callback_args=sensor)
# Get angle from IMU
gyroSub = rospy.Subscriber('gyro_sensor', Float64MultiArray, gyroCallback, callback_args=(sensor, thrusterPub))
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
  y_center = (path[2] + path[3])/2
  print(f"Starting alignment. Initial x_center: {x_center}, y_center: {y_center}")
  while abs(x_center - 0.5) > 0.05 or abs(y_center - 0.5) > 0.05:
    if abs(y_center - 0.5) > 0.05:
      # y-coordinate is not aligned
      if y_center > 0.5:
        # If path is at the upper part of the frame, move forward.
        print("Path is at the upper part of the frame, moving forward.")
        move("forward", sensor, thrusterPub, 0.1)
        bboxes = cvBottom()
        path = findObject("path", bboxes, cvDict)
        while(not path):
          # Path is no longer in the frame, which means we overshoot
          print("Path overshot, moving backward.")
          move("backward", sensor, thrusterPub, 0.01)
          bboxes = cvBottom()
          path = findObject("path", bboxes, cvDict)
      else:
        # Path is at the lower part of the frame, move backward.
        print("Path is at the lower part of the frame, moving backward.")
        move("backward", sensor, thrusterPub, 0.1)
        bboxes = cvBottom(sensor)
        path = findObject("path", bboxes, cvDict)
        while(not path):
          print("Path overshot, moving forward.")
          move("forward", sensor, thrusterPub, 0.01)
          bboxes = cvBottom(sensor)
          path = findObject("path", bboxes, cvDict)
    else:
      # x-coordinate is not aligned
      if x_center > 0.5: 
        # If path is at the right part of the frame, move right.
        print("Path is at the right part of the frame, moving to the right.")
        turn(90, sensor, thrusterPub)
        move("forward", sensor, thrusterPub, 0.1)
        turn(270, sensor, thrusterPub)
        bboxes = cvBottom(sensor)
        path = findObject("path", bboxes, cvDict)
        while(not path):
          print("Path overshot, moving left.")
          turn(270, sensor, thrusterPub)
          move("forward", sensor, thrusterPub, 0.01)
          turn(90, sensor, thrusterPub)
          bboxes = cvBottom(sensor)
          path = findObject("path", bboxes, cvDict)
      else:
        print("Path is at the left part of the frame, moving to the left.")
        turn(270, sensor, thrusterPub)
        move("forward", sensor, thrusterPub, 0.1)
        turn(90, sensor, thrusterPub)
        bboxes = cvBottom(sensor)
        path = findObject("path", bboxes, cvDict)
        while(not path):
          print("Path overshot, moving right.")
          turn(90, sensor, thrusterPub)
          move("forward", sensor, thrusterPub, 0.01)
          turn(270, sensor, thrusterPub)
          bboxes = cvBottom(sensor)
          path = findObject("path", bboxes, cvDict)
      x_center = (path[0] + path[1])/2
      y_center = (path[2] + path[3])/2
      print(f"Updated x_center: {x_center}, y_center: {y_center}")
    directPath(path)


def directPath(pathObj):
    # Use the width of the bounding box to determine the direction of the path.
    # At the start of the function, we are pointing away from the gate
    width = pathObj[1] - pathObj[0]
    length = pathObj[3] - pathObj[2]
    cur_ratio = length / width
    turning_angle = 0
    print(f"Initial ratio of length and width: {cur_ratio}, starting direction alignment.")

    # cur_ratio is the largest ratio
    for i in range(0, 90, 1):
        turn(1, sensor, thrusterPub)
        sleep(0.1)
        # Get the current bounding box ratio
        pathObj = cvBottom(sensor)
        width = pathObj[1] - pathObj[0]
        length = pathObj[3] - pathObj[2]
        new_ratio = length / width
        if new_ratio > cur_ratio:
            cur_ratio = new_ratio
            turning_angle = i
        print(f"Turned {i} degrees, new ratio: {new_ratio}, current best angle: {turning_angle}")

    turn(180, sensor, thrusterPub)
    print("Turned 180 degrees, checking the other side.")

    for i in range(0, 90, 1):
        turn(1, sensor, thrusterPub)
        sleep(0.1)
        # Get the current bounding box ratio
        width = pathObj[1] - pathObj[0]
        length = pathObj[3] - pathObj[2]
        new_ratio = length / width
        if new_ratio > cur_ratio:
            cur_ratio = new_ratio
            turning_angle = i + 270
        print(f"Turned {i + 90} degrees, new ratio: {new_ratio}, current best angle: {turning_angle}")

    # turning_angle with the largest ratio
    turn(turning_angle, sensor, thrusterPub)
    # robot facing the direction of the path marker
    print(f"Turned to the best angle: {turning_angle}. Robot is facing the path marker.")

def followThePath():
  # Find the path and then orient the robot in the direction of the path
  print("Finding the path and alighning the robot in the direction of the path.")
  changeDepth(1.5, sensor, thrusterPub)
  while True:
    turn(270, sensor, thrusterPub)
    # Move left from the point out of the gate for the gate's width while search for the gate
    for i in range(ceil(gate_width / step)):
      bboxes = cvBottom(sensor)
      path = findObject("path", bboxes, cvDict)
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
      path = findObject("path", bboxes, cvDict)
      if path:
        turn(270, sensor, thrusterPub)
        # If path is found, turn to point away from the gate and align the gate.
        alignPath(path)
        return
    print("Path not found, moving backward and retrying.")
    move("backward", sensor, thrusterPub, gate_width * 2)
    turn(270, sensor, thrusterPub)
    move("forward", sensor, thrusterPub, 1)

def alignVertical(obj):
  # Align the obj vertically.
  print('Aligning the object vertically')
  reachedBottom = False
  while (True):
    found = False
    for i in cv(sensor):
      # Detected the obj
      if i[4] == cvDict[obj]:
        y1 = i[2]
        y2 = i[3]

        y_center = (y1+y2)/2
        found = True
        if abs(y_center - 0.5) > 0.05:
          if y_center > 0.5:
            move("up", sensor, thrusterPub)
          else:
            move("down", sensor, thrusterPub)
        else:
          print('Object aligned vertically')
          return True

    if not found:
      print("Object not found, change depth to try to find the object")
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

  print("Starting the task to hit buoy.")
  # Change the depth to the depth of the buoy.
  changeDepth(0.9, sensor, thrusterPub)
  # Move until buoy is within sight.
  while not findObject("buoy", cv(sensor), cvDict):
    move("forward", sensor, thrusterPub)
  # Align buoy to the center of the frame both horizontally and vertically.
  alignVertical("buoy")
  alignObj("buoy", sensor, thrusterPub, cvDict)
  # Move until one of the two images of the correct class is within frame.
  bboxes = cv(sensor)
  while not findObject(classNum+"img2", bboxes, cvDict) and not findObject(classNum+"img2", bboxes, cvDict):
    move("forward", sensor, thrusterPub)
    bboxes = cv(sensor)
  # Assign one image of the correct class that is within the frame to be targetObj.
  targetObj = None
  if findObject(classNum+"img2", cv(sensor), cvDict):
    targetObj = classNum+"img2"
  else:
    targetObj = classNum+"img3"
  # Align targetObj to the center of the frame both horizontally and vertically.
  alignVertical(targetObj)
  alignObj(targetObj, sensor, thrusterPub, cvDict)
  # Move forward until the buoy is hit.
  while not sensor.get("touch"):
    move("forward", sensor, thrusterPub)  
  print("Buoy is successfully hit.")



def main():
  sleep(5)
  changeDepth(0.3, sensor, thrusterPub)
  searchGate("left", sensor, thrusterPub, cvDict)
  targetClass = None # The string for which class we are targeting.
  while not findObject("class1img1", cv(sensor), cvDict) and not findObject("class2img1", cv(sensor), cvDict):
    move("forward", sensor, thrusterPub)
  if findObject("class1img1", cv(sensor), cvDict):
    targetClass = "class1"
    alignObj("class1img1", sensor, thrusterPub, cvDict)
  else:
    targetClass = "class2"
    alignObj("class2img1", sensor, thrusterPub, cvDict)
  moveTillGone(targetClass+"img1", sensor, thrusterPub)
  for i in range(ceil(through_gate/step)):
    move("forward", sensor, thrusterPub)
  followThePath()
  buoy(targetClass)
  changeDepth(0, sensor, thrusterPub)


if __name__ == "__main__":
  main()
