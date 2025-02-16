# -*- coding: utf-8 -*-
"""IMU.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1SElfKHJ1-ea-xg-uKj-ULKaRa-3_ZPLQ

Download module from https://github.com/LORD-MicroStrain/MSCL/blob/master/HowToUseMSCL.md
"""

from win64_mscl import mscl
# import rospy
# from std_msgs.msg import Float64MultiArray
import math


TEST = True

port = "COM4"
baud = 115200

print()
#create the connection object with port and baud rate
connection = mscl.Connection.Serial(port, baud)

#create the InertialNode, passing in the connection
node = mscl.InertialNode(connection)

if TEST:
  success = node.ping()
  activeChs = node.getActiveChannelFields(mscl.MipTypes.CLASS_AHRS_IMU)
  print(success)
  print(activeChs)

exit()

imuChs = mscl.MipChannels()
# Add channel for change in velocity, unit is g*s
imuChs.append(mscl.MipChannel(mscl.MipTypes.CH_FIELD_SENSOR_DELTA_VELOCITY_VEC, mscl.SampleRate.Hertz(100)))
# Add channel for change in angle, unit is radian
imuChs.append(mscl.MipChannel(mscl.MipTypes.CH_FIELD_SENSOR_DELTA_THETA_VEC, mscl.SampleRate.Hertz(100)))

node.setActiveChannelFields(mscl.MipTypes.CLASS_AHRS_IMU, imuChs)

node.enableDataStream(mscl.MipTypes.CLASS_AHRS_IMU)

rospy.init_node('IMU_pub', anonymous=True)
distancePub = rospy.Publisher('displacement_sensor', Float64MultiArray, queue_size=10)
gyroPub = rospy.Publisher('gyro_sensor', Float64MultiArray, queue_size=10)

# Initial angle, distance, and velocity. Each element represent axis X, Y, Z.
# Unit is degree
angles = [0, 0, 0]
# Unit is meter
displacements = [0, 0, 0]
# Unit is m/s
velocity = [0, 0, 0]
# The last timestamp for velocity update
vel_time = [0, 0, 0]

while True:
    # get all the packets that have been collected, with a timeout of 10 milliseconds
    packets = node.getDataPackets(100)
    for packet in packets:
        # get all of the points in the packet
        points = packet.data()
        if TEST:
          print("Description: ", packet.descriptorSet())
          print("Points: ", points)

        for dataPoint in points:
          if TEST:
            print("Channel name: ", dataPoint.channelName())   # the name of the channel for this point
            print("Channel field: ", dataPoint.field())
            print("Channel qualifier: ", dataPoint.qualifier())
            print("Value type: ", dataPoint.storedAs())      # the ValueType that the data is stored as
            print("Value: ", dataPoint.as_float())      # get the value as a float

          value = dataPoint.as_float()
          qualifier = dataPoint.qualifier()
          if dataPoint.field() == mscl.MipTypes.CH_FIELD_SENSOR_DELTA_THETA_VEC:
            # Convert from radian to degree
            value = value / math.pi * 180
            if qualifier == mscl.MipTypes.CH_X:
              angles[0] += value
            elif qualifier == mscl.MipTypes.CH_Y:
              angles[1] += value
            elif qualifier == mscl.MipTypes.CH_Z:
              angles[2] += value
          elif dataPoint.field() == mscl.MipTypes.CH_FIELD_SENSOR_DELTA_VELOCITY_VEC:
            time = dataPoint.collectedTimestamp()
            ind = -1
            if qualifier == mscl.MipTypes.CH_X:
              ind = 0
            elif qualifier == mscl.MipTypes.CH_Y:
              ind = 1
            elif qualifier == mscl.MipTypes.CH_Z:
              ind = 2
            else:
              continue
            timespan = time - vel_time[ind]
            nanosecond = timespan.getNanoseconds()

            # Convert change in velocity from g*s to m/s
            value = value * 9.8

            # Use average velocity during the period to calculate displacement, assuming linear change in velocity
            displacement = (velocity[ind] + 1/2 * value) * nanosecond / (10**9)

            vel_time[ind] = time
            velocity[ind] += value
            displacements[ind] += displacement



        if not rospy.is_shutdown():
          angleMsg = Float64MultiArray()
          angleMsg.data = angles
          distanceMsg = Float64MultiArray()
          distanceMsg.data = displacements
          gyroPub.publish(angleMsg)
          distancePub.publish(distanceMsg)