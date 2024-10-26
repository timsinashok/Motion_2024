# -*- coding: utf-8 -*-
"""util.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Z6j1h4NaKWoPxip77ZwgNpgCsN1AVjFH
"""

import Serial
import rospy
from std_msgs.msg import Float64MultiArray, String, Float64, Bool, Int32MultiArray
from math import *
from time import time, sleep


# Threshold for temperature and moisture
TEMP_T = 100
LEAK_T = 10

def unflatten(data, length=5):
  # Convert the CV data to a list of list
  if len(data) % length != 0:
    print("Wrong data")
    return []
  output_count = int(len(data) / length)
  result = []
  for i in range(output_count):
    bbox = []
    for j in range(length*i, length*(i+1)):
      bbox.append(float(data[j]))
    result.append(bbox)
  return result


def cvCallback(data, sensor):
  # sensor is the object to be modified
  # Computer vision: A list of bounding boxes [x1, x2, y1, y2, class]. (x1, y1) is the top left corner. (x2, y2) is the bottom right corner. Coordinates from 0-1
  sensor["CV_result"] = unflatten(data)


def cv(sensor):
  # Return the copy of computer vision data to avoid the risk of CV_result being modified while being processed
  return sensor.get("CV_result").deepcopy()


def cvBottomCallback(data, sensor):
  sensor["CV_bottom"] = unflatten(data)


def cvBottom(sensor):
  return sensor.get("CV_bottom").deepcopy()


def findObject(object, bboxes, cvDict):
  # Look for the object in the list of bounding boxes
  # bboxes is a list of bounding boxes.
  found = False
  for i in bboxes:
    if i[4] == cvDict[object]:
      return i
  return False


def move(direction, sensor, thrusterPub, distance=0.2):
  # direction can be "forward", "backward", "left", "right", "up", "down"
  # Default distance to move is 0.2 m each time
  # 0.2 m correspond to 5 degrees when turning left and right
  # Turn 5 degree at a time
  message = []
  # 0 for forward and backward, 1 for turning, 2 for changing depth, 3 for pitch and 4 for roll
  if direction == "forward":
    PIDxy(sensor, distance, thrusterPub)
  elif direction == "backward":
    PIDxy(sensor, -distance, thrusterPub)
  elif direction == "left":
    PIDturn(sensor, -distance*25, thrusterPub)
  elif direction == "right":
    PIDturn(sensor, distance*25, thrusterPub)
  elif direction == "up":
    PIDdepth(sensor, distance, thrusterPub)
  elif direction == "down":
    PIDdepth(sensor, -distance, thrusterPub)
  else:
    print("Invalid input: ", direction)
    return


def depthCallback(data, sensor):
  sensor["depth"] = float(data)


def pressureCallback(data, sensor):
  sensor["pressure"] = float(data)


def gyroCallback(data, sensor, thrusterPub):
  # The angles on x-axis, y-axis, and z-axis from gyrometer. Format is 360 degrees. angles[2] is suppose to be the horizontal angle 
  # angle[0] is angle with x-axis used for pitch 
  # angle[1] is angle with y-axis used for roll
  # angle[2] is angle with z-axis used for yaw -> turn

  angles = []
  for i in range(len(data)):
    angles.append(float(data[i]))
  sensor["angles"] = angles

  # if we are not doing roll ourself adjust the pitch and roll to stablize 
  if not sensor["pitch"] and abs(angles[0]) > 1:
    sensor["pitch"] = True
    PIDpitch(sensor, -angles[0] , thrusterPub)
    sensor["pitch"] = False

  if not sensor["roll"] and abs(angles[1]) > 1:
    sensor["roll"] = True
    PIDpitch(sensor, -angles[1] , thrusterPub)
    sensor["roll"] = False


def distanceCallback(data, sensor):
  sensor["distance"] = data


def touchCallback(data,sensor):
  sensor['touch'] = bool(data)


def temperatureCallback(data, sensor, thrusterPub):
  # Callback function for the temperature sensor subscriber
  sensor['temperature'] = float(data)
  if data > TEMP_T:
    endRun(sensor, thrusterPub)


def leakCallback(data, sensor, thrusterPub):
  # Callback function for the leak sensor subscriber
  sensor['leak'] = data # data is float
  if data > LEAK_T: # if data is greater than the threshold
    endRun(sensor, thrusterPub)


def endRun(sensor, thrusterPub):
  # Make the robot move to the surface and end the program.
  changeDepth(0, sensor, thrusterPub)
  exit()

def changeDepth(target, sensor, thrusterPub):
  # Change the depth to target meters above the bottom of the pool. Depth from camera being used
  # If target is negative or 0, the target is meter below the top of the pool. Pressure sensor being used.
  initial_depth = 0
  if target > 0:
    while abs(sensor.get("depth") - target) > 0.1:
      if sensor.get("depth") > target:
        move("down", sensor, thrusterPub)
      else:
        move("up", sensor, thrusterPub)
  else:
    while abs(sensor.get("pressure")-abs(target)) > 0.1:
      if sensor.get("pressure") < abs(target):
        move("down", sensor, thrusterPub)
      else:
        move("up", sensor, thrusterPub)


def turn(degree, sensor, thrusterPub):
  # Turn degree clockwise. Does not support negative
  initAngle = sensor.get("angles")[2]
  if degree > 180:
    move("left", sensor, thrusterPub, degree-180)
  else:
    move("right", sensor, thrusterPub, degree)
  angleDiff = (sensor.get("angles")[2] - initAngle) % 360
  while abs(angleDiff - degree) >= 5:
    if angleDiff < degree and degree - angleDiff < 180:
      move("right", sensor, thrusterPub)
    else:
      move("left", sensor, thrusterPub)
    angleDiff = (sensor.get("angles")[2] - initAngle) % 360


def searchGate(target, sensor, thrusterPub, cvDict):
  # Find the gate and point target.
  # Steps:
  # 1. Reotate right until find one pole, record its angle
  # 2. Rotate right until find second pole, record its angle
  # 3. Calculate difference in angle, if difference less than 180, turn left until facing center/left center of poles
  # 4. If difference larger than 180, turn right until facing center/left center of poles.

  # target can be set to "center" or "left", which the center of the gate or the midpoint between left pole and center of the gate.
  # poleFound is the number of pole whose angle has been determined.
  poleFound = 0
  poleAngle = [0, 0]
  prevPoleCenter = None
  marginOfError = 0.05
  while (True):
    # Get a list of bounding boxes [x1, x2, y1, y2, class]. (x1, y1) is the top left corner. (x2, y2) is the bottom right corner. Coordinates from 0-1
    bboxes = cv(sensor)
    # poleCount is the number of poles detected
    poleCount = 0
    # curPoleCenter records the x-coordinate of the center of the poles detected.
    curPoleCenter = []
    for bbox in bboxes:
      if bbox[4] == cvDict['pole']:
        poleCount += 1
        # Add the x-coordinate of the middle of the pole that is detected.
        curPoleCenter.append((bbox[0] + bbox[1])/2)

    # The pole at the center of the frame
    centeredPole = None

    # Decide action based on the number of poles in the image
    if poleCount == 1 and abs(curPoleCenter[0] - 0.5) < marginOfError:
      # If one pole is detected and that pole is in the center of the frame.
        centeredPole =  curPoleCenter[0]
    elif poleCount == 2:
      # Two poles are found in the same frame
      if abs(curPoleCenter[0] - 0.5) < marginOfError:
        centeredPole = curPoleCenter[0]
      elif abs(curPoleCenter[1] - 0.5) < marginOfError:
        centeredPole = curPoleCenter[1]
    # No pole found otherwise


    if centeredPole:
        # Decide whether this pole is different from last pole whose angle is stored.
        if not prevPoleCenter:
          # No pole in the last frame, this is a new pole
          poleFound += 1
        elif prevPoleCenter < centeredPole:
          # The pole in previous frame is left of the pole in the current frame.
          # As the robot is moving right, the pole is a new pole
          poleFound += 1

        # Otherwise, the pole in previous frame is right of the pole in the current frame.
        # As the robot is moving right, the pole is the previous pole
        poleAngle[poleFound - 1] = sensor.get("angles")[2]
        prevPoleCenter = centeredPole
        if poleFound ==2:
          # Both pole has been found. Decide where is the gate based on the angles
          angleDifference = (poleAngle[1] - poleAngle[0]) % 360
          # Add angle difference to the pole
          if angleDifference > 180:
            # The difference in angle of pole 2 and pole 1 is larger than 180
            # The gate must be behind the curve of rotation.
            if target == "center":
              targetAngle = ((360 - angleDifference) / 2 + poleAngle[1]) % 360
              turn((sensor.get("angles")[2] -targetAngle)%360)
            elif target == "left":
              targetAngle = ((360 - angleDifference) / 4 + poleAngle[1]) % 360
              turn((sensor.get("angles")[2] -targetAngle)%360)
          else:
            if target == "center":
              targetAngle = (angleDifference / 2 + poleAngle[0]) % 360
              turn((sensor.get("angles")[2] -targetAngle)%360)
            elif target == "left":
              targetAngle = (angleDifference / 4 + poleAngle[0]) % 360
              turn((sensor.get("angles")[2] -targetAngle)%360)
          return True
    # Turn until we find at least one pole on the gate
    move("right", sensor, thrusterPub)


def alignObj(obj, sensor, thrusterPub, cvDict, axis=0.5):
  # ALign horizontally to ensure the specified object is at a specific part of the camera frame.
  while (True):
    for i in cv(sensor):
      # Detected the marker
      if i[4] == cvDict[obj]:
        x1 = i[0]
        x2 = i[1]
        if (abs((x1+x2)/2)-axis)<=0.05:
          # Return the width of the marker
          return (x2-x1)
        elif abs(axis - x1) < abs(x2 - axis):
          move('right', sensor)
        else:
          move('left', sensor)
    # Marker not detected by cv
    move("right", sensor, thrusterPub)


def moveTillGone(object, sensor, thrusterPub, cvDict):
  counter = 0
  while True:
    result = findObject(object, cv(sensor), cvDict)
    if result:
      move("forward", sensor, thrusterPub)
      counter += 1
    else:
      return counter


def PID(Kp, Ki, Kd, e, time_prev, e_prev, integral):
    time = time()

    # PID calculations
    P = Kp*e
    integral = integral + Ki*e*(time - time_prev)
    D = Kd*(e - e_prev)/(time - time_prev + 1e-6)

    # calculate manipulated variable - MV
    MV = P + integral + D

    return MV, time, integral


def PIDxy(sensor, target, thrusterPub):
  # Move target distance in the xy plane, target can be negative
  start_x = sensor.get("distance")[0]
  start_y = sensor.get("distance")[1]
  target_x = start_x + cos(sensor.get("angles")[2]) * target
  target_y = start_y + sin(sensor.get("angles")[2]) * target
  time_prev = time()
  e_prev = 0
  integral = 0
  while True:
    cur_x = sensor.get("distance")[0]
    cur_y = sensor.get("distance")[1]
    e = ((target_x - cur_x)**2 + (target_y - cur_y)**2)**0.5
    speed, time_prev, integral = PID(1, 0.5, 0.1, e, time_prev, e_prev, integral)
    e_prev = e
    # speed is m/s^2
    message = []
    if speed < 0.001 and abs(e_prev) < 0.1:
      message.append(0)
      message.append(0)
      thrusterPub.publish(Int32MultiArray(message))
      break
    else:
      message.append(0)
      message.append(round(speed))
      thrusterPub.publish(Int32MultiArray(message))
    sleep(0.001)


def PIDturn(sensor, target, thrusterPub):
  # turn the target angle, clockwise is positive
  start = sensor.get("angles")[2]
  target = start + target
  time_prev = time()
  e_prev = 0
  integral = 0
  while True:
    e = target - sensor.get("angles")[2]
    speed, time_prev, integral = PID(1, 0.5, 0.1, e, time_prev, e_prev, integral) #cur_distance not defined
    e_prev = e
    # speed is degree/s^2
    message = []
    if speed < 0.001 and abs(e_prev) < 1:
      message.append(1)
      message.append(0)
      thrusterPub.publish(Int32MultiArray(message))
      break
    else:
      message.append(1)
      message.append(round(speed))
      thrusterPub.publish(Int32MultiArray(message))
    sleep(0.001)

def PIDdepth(sensor, target, thrusterPub):
    # Move up the target distance. target can be negative
    start = sensor.get("depth")
    target = start + target
    time_prev = time()
    e_prev = 0
    integral = 0
    while True:
      e = target - sensor.get("depth")
      speed, time_prev, integral = PID(1, 0.5, 0.1, e, time_prev, e_prev, integral)
      e_prev = e
      # speed is degree/s^2
      message = []
      if speed < 0.001 and abs(e_prev) < 0.1:
        message.append(2)
        message.append(0)
        thrusterPub.publish(Int32MultiArray(message))
        break
      else:
        message.append(2)
        message.append(round(speed))
        thrusterPub.publish(Int32MultiArray(message))
      sleep(0.001)


def PIDpitch(sensor, target, thrusterPub):
  # Move the target angle in pitch. Clockwise is positive
  start = sensor['angles'][0] # angle with x-axis
  target = start + target
  time_prev = time()
  e_prev = 0
  integral = 0
  while True:
    e = target - sensor.get("angles")[0] # error
    speed, time_prev, integral = PID(1, 0.5, 0.1, e, time_prev, e_prev, integral) #cur_distance not defined
    e_prev = e
    # speed is degree/s^2
    message = []
    if speed < 0.001 and abs(e_prev) < 1:
      message.append(3) # 3 for pitch
      message.append(0)
      thrusterPub.publish(Int32MultiArray(message))
      break
    else:
      message.append(3)
      message.append(round(speed))
      thrusterPub.publish(Int32MultiArray(message))
    sleep(0.001)

def PIDroll(sensor, target, thrusterPub):
  # Move the target angle in roll. Clockwise is positive
  start = sensor['angles'][1] # angle with y-axis
  target = start + target
  time_prev = time()
  e_prev = 0
  integral = 0
  while True:
    e = target - sensor.get("angles")[1] # error
    speed, time_prev, integral = PID(1, 0.5, 0.1, e, time_prev, e_prev, integral) #cur_distance not defined
    e_prev = e
    # speed is degree/s^2
    message = []
    if speed < 0.001 and abs(e_prev) < 1:
      message.append(4) # 4 for roll
      message.append(0)
      thrusterPub.publish(Int32MultiArray(message))
      break
    else:
      message.append(4)
      message.append(round(speed))
      thrusterPub.publish(Int32MultiArray(message))
    sleep(0.001)




