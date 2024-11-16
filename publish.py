import rospy
import ast
from time import sleep
from std_msgs.msg import Float64MultiArray, Float64, Int32MultiArray, Bool
from util import cvCallback, depthCallback, gyroCallback, cv, turn, changeDepth, searchGate, move, moveTillGone, touchCallback, distanceCallback


if __name__ == '__main__':
    rospy.init_node('publish')

    cvPub = rospy.Publisher('CV', Float64MultiArray)
    depthPub = rospy.Publisher('depth_sensor', Float64)
    gyroPub = rospy.Publisher('gyro_sensor', Float64)
    distancePub = rospy.Publisher('displacement_sensor', Float64)
    pressurePub = rospy.Publisher("pressure_sensor", Float64)

    #prevyear
    cvBottomPub = rospy.Publisher('CV_bottom', Float64MultiArray)
    
    
    initial_CV = Float64MultiArray()
    initial_CV.data = []
    initial_depth = Float64(2.0)
    initial_gyro = Float64MultiArray()
    initial_gyro.data = [0, 0, 0]
    initial_distance = Float64MultiArray()
    initial_distance.data = [0, 0, 0]
    initial_CV_bottom = Float64MultiArray()
    initial_CV_bottom.data = []
    initial_pressure = Float64(0)
    cvPub.publish(initial_CV)
    depthPub.publish(initial_depth)
    gyroPub.publish(initial_gyro)
    distancePub.publish(initial_distance)
    cvBottomPub.publish(initial_CV_bottom)
    pressurePub.publish(initial_pressure)
     


    while not rospy.is_shutdown():
        topic = input("Topic: ").upper()
        msg = input("Message: ")
        if topic == "CV":
            msg = ast.literal_eval(msg)
            cvMsg = Float64MultiArray()
            cvMsg.data = msg
            cvPub.publish(cvMsg)
        elif topic == "DEPTH":
            depthF = float(msg)
            depthMsg = Float64(depthF)
            depthPub.publish(depthMsg)
        elif topic == "GYRO":
            gyroF = float(msg)
            gyroMsg = Float64(gyroF)
            gyroPub.publish(gyroMsg)
        elif topic == "DISTANCE":
            msg = ast.literal_eval(msg)
            distanceMsg = Float64MultiArray()
            distanceMsg.data = msg
            distancePub.publish(distanceMsg)
        elif topic == "CV_BOTTOM":
            msg = ast.literal_eval(msg)
            cvBottomMsg = Float64MultiArray()
            cvBottomMsg.data = msg
            cvBottomPub.publish(cvBottomMsg)
        elif topic == "PRESSURE":
            pressureF = float(msg)
            pressureMsg = Float64(pressureF)
            pressurePub.publish(pressureMsg)
        else:
            print("Invalid topic")


