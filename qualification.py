# -*- coding: utf-8 -*-
"""qualification.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1itgeQcYcsfPFC-nFoW3NXKFqgZGDUW-V
"""

# @title
#                   ***General Outline     ***
# 1) Submerge down to 0.5 meters away from floor
# 2) Turn until we find at least one pole on the gate
#   2a) Rotate until we see the secont pole, update timer
#   2b) Rotate again until we hit the first pole again, then slightly over face the inside the gate
# 3) Move forward until the marker is within the CV detection
#   3a) Turn left until marker is > 75% in image
#   3b) Move forward until marker disappears in CV
#   3c) Turn right 90 degrees and check marker's location in image.
#   3d) If marker is in the right portion of the image, move forward.
# 4) Repeat step 3b to 3d
# 5) Once the gate is within view, break out of turning loop and move forward
# 6) Re-execute the preliminary gate code/function
# 7) Pass through gate
# 8) Move forward until 0.5 meters away from the wall
# 9) Surface the sub!

# Computer vision: A list of bounding boxes [x1, x2, y1, y2, class]. (x1, y1) is the top left corner. (x2, y2) is the bottom right corner. Coordinates from 0-1
import rospy
from rospy import sleep
from std_msgs.msg import Float64MultiArray, Float64, Int32MultiArray
from util import cvCallback, depthCallback, gyroCallback, cv, turn, changeDepth, searchGate, move, moveTillGone, distanceCallback, pressureCallback


rospy.init_node('qualification', anonymous=True)
# The number of move forward needed to move through the gate after gate poles are out of sight.
through_gate = 3.5

sensor = {}

# Subscribe to the CV output
cvSub = rospy.Subscriber('CV', Float64MultiArray, cvCallback, callback_args=sensor)
thrusterPub = rospy.Publisher("thruster", Int32MultiArray)

#Subscribing to the depth sensor
depthSub = rospy.Subscriber('depth_sensor', Float64, depthCallback, callback_args=sensor)
pressureSub = rospy.Subscriber('pressure_sensor', Float64, pressureCallback, callback_args=sensor)

# Subscribing to IMU to get angle
gyroSub = rospy.Subscriber('gyro_sensor', Float64MultiArray, gyroCallback, callback_args=(sensor, thrusterPub))

# Subscribe to IMU to get distance
distanceSub = rospy.Subscriber("displacement_sensor", Float64MultiArray, distanceCallback, callback_args=sensor)

# Contain the class number for each object
CV_dictionary = {"pole":0, "marker": 1}


def alignMarker(axis):
  # Ensure marker is at the axis at the specific x-coordinate.
  while (True):
    for i in cv():
      # Detected the marker
      if i[4] == CV_dictionary['marker']:
        x1 = i[0]
        x2 = i[1]
        if (abs((x1+x2)/2)-axis)<=0.05:
          # Return the width of the marker
          return (x2-x1)
        elif abs(axis - x1) < abs(x2 - axis):
          move('right', sensor, thrusterPub)
        else:
          move('left', sensor, thrusterPub)
    # Marker not detected by cv
    move("right", sensor, thrusterPub)




def objectCaptured(object):
  # Check whether the object is captured by the camera
  # Return the x-coordinates of the center of the object
  for i in cv():
    if i[4] == CV_dictionary[object]:
      print(object ," captured by the camera, the x-coordinates is: ", (i[0] + i[1]) / 2)
      return (i[0] + i[1]) / 2
  print("NO ", object, " captured by the camera")
  return -1


def aroundMarker():
# Get close to the marker
# Take a left turn
# Keep going forward til the marker is not visible
# Turn right
# Keep going forward until marker is not visible
# Turn right
  print("Around marker begins")
  sleep(5)
  while True:
    width = alignMarker(0.5)
    if width > 0.2:
      break
    move("forward", sensor, thrusterPub)
  alignMarker(0.8) 
  distanceMoved = moveTillGone("marker", sensor, thrusterPub)
  turn(90, sensor, thrusterPub)
  captured = objectCaptured("marker")
  # Move forward until the marker is right of the 0.7 axis when sub is turned toward the marker.
  # This ensures the submarine
  while captured < 0.7:
    # Turn left 90, move forward, turn right 90, check position of marker
    turn(270, sensor, thrusterPub)
    move("forward", sensor, thrusterPub)
    distanceMoved += 0.2
    turn(90, sensor, thrusterPub)
    captured = objectCaptured("marker")
  moveTillGone("marker", sensor, thrusterPub)
  turn(90, sensor, thrusterPub)
  captured = objectCaptured("marker")
  while captured < 0.7:
    turn(270, sensor, thrusterPub)
    move("forward", sensor, thrusterPub)
    turn(90, sensor, thrusterPub)
    captured = objectCaptured("marker")
  # Move back the same distance as move forward
  move("forward", sensor, thrusterPub, distance=distanceMoved)
  print("Around marker ends")

def main():
  print("Manual testing data: 15 seconds")
  sleep(15)
  print("Qualification Start")
  sleep(5)
  print(sensor)
  changeDepth(0.3, sensor, thrusterPub)
  searchGate("center", sensor, thrusterPub, CV_dictionary)
  moveTillGone("pole", sensor, thrusterPub)
  print("Getting close to gate")
  move("forward", sensor, thrusterPub, distance=through_gate)
  aroundMarker()
  searchGate("center", sensor, thrusterPub, CV_dictionary)
  moveTillGone("pole", sensor, thrusterPub)
  for i in range(through_gate):
    move("forward", sensor, thrusterPub)


if __name__ == "__main__":
  main()