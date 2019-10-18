import numpy as np
import cv2
import time
import matplotlib
import sys
matplotlib.use('TkAgg') # See https://stackoverflow.com/questions/32019556/matplotlib-crashing-tkinter-application
import matplotlib.pyplot as plt
import warnings
warnings.simplefilter('ignore', np.RankWarning)




class Image():

    # COLORS for LINES
    LINE_COLOR = (64, 21, 183)

    # ROI Polygons
    MOTORCYCLE = np.array([
                    (0,200),
                    (800,200),
                    (800,440),
                    (0,440)
                ],dtype=np.int32)

    SCOOTER = np.array([
                    (0,450),
                    (800,450),
                    (556,196),
                    (224,196),
                    (0,306)
                ],dtype=np.int32)

    # real.mp4 is 1271x712
    REAL_POLY = np.array([
        (200, 712),
        (1100, 712),
        (550,250)
    ], dtype=np.int32)


    def __init__(self, image):
        self.image = image
        self.edges_image = np.zeros_like(self.image)
        self.processed_image = np.zeros_like(self.image)
        self.hough_lane_overlay = np.zeros_like(self.image) # Intermediary overlay generated by combining the original image with the Hough-transformed lines
        self.lane_lines = np.zeros_like(self.image) # lines generated by Hough transformation
        self.line_avg = np.zeros_like(self.image) # avg lines for left/right side (without any overlay)
        self.lane_overlay = np.zeros_like(self.image) # Final overlay generated by the averaged lines overlay (based off hough line calculations)
          
        self.hough_lines = np.array([])

    def show(self, version='processed'):
        versions = {
            'original': self.image,
            'edges': self.edges_image, 
            'processed': self.processed_image,
            'lines': self.lane_lines, # lines generated by Hough transformation
            'hough_overlay': self.hough_lane_overlay, # Intermediary overlay generated by combining the original image with the Hough-transformed lines
            'overlay': self.lane_overlay # Final overlay generated by the averaged lines overlay (based off hough line calculations)
        }
        cv2.imshow('image', versions[version])
        cv2.waitKey(0)

    def show_original(self):
        cv2.imshow('image', self.image)
        cv2.waitKey(0)

    '''
    Convert the image to grayscale to deal with 1 channel instead of 3 channels (BGR)
    '''
    def convert_to_grayscale(self):
        self.processed_image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)

    '''
    Apply Gaussian blur to the image to reduce artifacts (see README for effects of blur vs no blur on edge detection)
    '''
    def blur(self, ksize=7):
        self.processed_image = cv2.GaussianBlur(self.processed_image, (ksize,ksize), 0)

    '''
    Detect edges with Canny Edge detector
    '''    
    def detect_edges(self, low_threshold = 50, high_threshold = 150):
        self.processed_image = cv2.Canny(self.processed_image, low_threshold, high_threshold)
        self.edges_image = self.processed_image

    '''
    Define the ROI (Region of Interest) as a mask and mask the image. 
    The shape of the mask will likely change based on the vehicle type.
    '''
    def apply_roi_mask(self, vehicle_type=REAL_POLY):
        mask = np.zeros_like(self.processed_image)
        cv2.fillPoly(mask, [vehicle_type], 255)
        self.processed_image = cv2.bitwise_and(self.processed_image, mask)

    '''
    this is "display_lines" in the YouTube tutorial
      
    Our image (and lanes) will likely have broken lines. Hough Transformation
    will identify straight lines for us even if they're not necessarily 
    connected. Imagine a bin of rows and columns. In each square, there may be
    points in which lines pass. The more points in the square, the more likely that
    a straight line is going through them. The larger the bins, the more points you
    pay get, but the less precision the lines will have. Don't go too small, it 
    will take longer and could result in innacuracies.

    theta (int): pixels of precision 
    rho (float): degree of precision, in radians. 1 radian = np.pi/180
    threshold: look for bin with highest number of "votes" on whether or not a line exists
    min_line_length: minimum length of a line we will accept
    max_line_gap: max gap distance between pixels in a line
    draw_to_original = Write to the original image if true, if not, write to the processed image
    '''
    def draw_hough_lines(self, theta=2, rho=np.pi/180, threshold=100, max_line_gap=40, min_line_length=100, thickness=5):
        lines = cv2.HoughLinesP(self.processed_image, theta, rho, threshold, np.array([]), minLineLength=min_line_length, maxLineGap=max_line_gap) 
        self.hough_lines = lines
        line_image = np.zeros_like(self.image)
        if lines is not None:
            for line in lines: # line is a 2D array, (x1, y1, x2, y2)
                x1, y1, x2, y2 = line.reshape(4)  # convert to a 1D array with 4 elements
                cv2.line(line_image, (x1, y1),  (x2, y2), self.LINE_COLOR, thickness)

        self.lane_lines = line_image
        self.hough_lane_overlay = cv2.addWeighted(self.image, 0.8, line_image, 1, 1)

    '''
    Draw the average lane lines based off Hough lines.
    Needs the original colored image, plus the Hough lines values
    '''
    def draw_averaged_lines(self, thickness=15):
        lane_image = self.image
        lines = self.hough_lines

        left_fit = []
        right_fit = []
        line_image = np.zeros_like(self.image)

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line.reshape(4)
                slope, intercept = np.polyfit((x1, x2), (y1, y2), 1) # 1 degree polynomial for a straight line
                if slope < 0:
                    left_fit.append((slope, intercept))
                elif slope > 0:
                    right_fit.append((slope, intercept))

            avg_lines = []

            if len(left_fit) > 0:
                left_fit_average = np.average(left_fit, axis=0)
                left_line = self.make_coordinates(self.image, left_fit_average)
                avg_lines.append(left_line)

            if len(right_fit) > 0:
                right_fit_average = np.average(right_fit, axis=0)   
                right_line = self.make_coordinates(self.image, right_fit_average)
                avg_lines.append(right_line)
    
            if avg_lines is not None:
                for line in avg_lines: # line is a 2D array, (x1, y1, x2, y2)
                    x1, y1, x2, y2 = line.reshape(4)  # convert to a 1D array with 4 elements
                    
                    try:
                        cv2.line(line_image, (x1, y1),  (x2, y2), self.LINE_COLOR, thickness)
                    except OverflowError:
                        pass
                    except TypeError:
                        pass

        self.line_avg = line_image

        self.lane_overlay = cv2.addWeighted(self.image, 0.8, line_image, 1, 1)
            
        return 

    '''
    Take the averaged lines and make (x1, y1) - (x2, y2) points for them.
    '''
    def make_coordinates(self, image, line_parameters):

        slope, intercept = line_parameters
        # y = mx + b; 
        # x = (y-b) / m

        y1 = image.shape[0]      # We have the max Y value
        y2 = int(y1 * .60)       # For the min Y, play around with this number for different results
        x1 = int((y1 - intercept) / slope)
        x2 = int((y2 - intercept) / slope)

        return np.array([x1, y1, x2, y2])


    '''
    Process the image, which includes
        1. Conversion from RGB(BGR) -> Grayscale
        2. Gaussian blurring (optional since edge detection does this)
        3. Edge Detection
        4. Masking the ROI (Region Of Interest)
    '''
    def process(self):
        self.convert_to_grayscale()
        self.blur()
        self.detect_edges()
        # self.apply_roi_mask(self.SCOOTER)
        self.draw_hough_lines()
        self.draw_averaged_lines()

cap = cv2.VideoCapture('robotcam.m4v')

t = 0
while(cap.isOpened()):
    _, original = cap.read()
    if original is not None:

        frame = Image(original)
        frame.process()

        # t+=1

        # if t>80:
        #     plt.imshow(original)   
        #     plt.show()

        # Temp to see processed image and the overlay lines
        # proccessed_plus_avg = cv2.addWeighted(cv2.cvtColor(frame.processed_image,cv2.COLOR_GRAY2BGR), 0.8, frame.line_avg, 1, 1)

        cv2.imshow('window', frame.lane_overlay)
        if cv2.waitKey(1) == ord('q'):
            break
    else:
        break

