import cv2
import face_recognition
import numpy as np
import json
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class FaceRecognizer:
    def __init__(self, faces_dir: str = "faces"):
        self.faces_dir = Path(faces_dir)
        self.known_face_encodings: List[np.ndarray] = []
        self.known_face_names: List[str] = []
        self.face_locations: List[Tuple[int, int, int, int]] = []
        self.face_encodings: List[np.ndarray] = []
        self.face_names: List[str] = []
        self.process_this_frame = True
        
        # Create faces directory if it doesn't exist
        if not self.faces_dir.exists():
            self.faces_dir.mkdir()
            logger.info(f"Created faces directory at {self.faces_dir}")
            
        self._load_known_faces()
        
    def _load_known_faces(self):
        """Load all known faces from the faces directory."""
        if not self.faces_dir.exists():
            logger.warning("Faces directory not found!")
            return
            
        for face_file in self.faces_dir.glob("*.jpeg"):
            try:
                # Load image file using OpenCV
                image = cv2.imread(str(face_file))
                if image is None:
                    logger.error(f"Failed to load image: {face_file}")
                    continue
                    
                # Convert BGR to RGB
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # Get face encodings
                face_encoding = face_recognition.face_encodings(rgb_image)
                
                if len(face_encoding) > 0:
                    # Get employee code from filename
                    employee_code = face_file.stem
                    
                    # Add to known faces
                    self.known_face_encodings.append(face_encoding[0])
                    self.known_face_names.append(employee_code)
                    logger.info(f"Loaded face for employee {employee_code}")
                else:
                    logger.warning(f"No face found in {face_file}")
                    
            except Exception as e:
                logger.error(f"Error loading face from {face_file}: {str(e)}")
                
        logger.info(f"Loaded {len(self.known_face_names)} known faces")
        
    def recognize_faces(self, frame) -> Optional[str]:
        """
        Recognize faces in the frame and return the employee code if a match is found.
        """
        # Resize frame for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        
        # Convert the image from BGR color to RGB
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Only process every other frame to save time
        if self.process_this_frame:
            # Find all face locations and face encodings in the current frame
            self.face_locations = face_recognition.face_locations(rgb_small_frame)
            self.face_encodings = face_recognition.face_encodings(rgb_small_frame, self.face_locations)
            
            self.face_names = []
            for face_encoding in self.face_encodings:
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.6)
                name = "Unknown"
                
                if True in matches:
                    # Use the known face with the smallest distance to the new face
                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = self.known_face_names[best_match_index]
                        
                self.face_names.append(name)
                
        self.process_this_frame = not self.process_this_frame
        
        # Return the first recognized employee code, or None if no match
        for name in self.face_names:
            if name != "Unknown":
                return name
                
        return None
        
    def draw_face_boxes(self, frame) -> None:
        """Draw boxes around faces and display names."""
        # Display the results
        for (top, right, bottom, left), name in zip(self.face_locations, self.face_names):
            # Scale back up face locations
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            
            # Draw a box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            
            # Draw a label with a name below the face
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1) 