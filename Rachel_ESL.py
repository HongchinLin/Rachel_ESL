#
#
# Command-Line Execution
# exec(open("./rachel.py").read())
#
# Multi-threading
# https://realpython.com/python-pyqt-qthread/

# Compile the Qt Designer file to a Python file.
# pyuic5 -x test_gui.ui -o test_gui.py

from PyQt5 import QtCore, QtGui, QtWidgets
# from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QDialog, QFileDialog

import sys
import time
from os import path

# https://pyttsx3.readthedocs.io/en/latest/engine.html
import pyttsx3
#
from sys import byteorder
from array import array
from struct import pack
import pyaudio
import wave
# pip install python-vlc
import vlc
#
import speech_recognition as sr
# From the Qt Designer file "test_gui.ui"
# Convert from ".ui" to ".py": pyuic5 -x test_gui.ui -o test_gui.py
from test_gui import Ui_read_text


class Recording():
    def __init__(self, THRESHOLD=500, CHUNK_SIZE=1024, RATE=44100):
        self.THRESHOLD = THRESHOLD
        self.CHUNK_SIZE = CHUNK_SIZE
        self.FORMAT = pyaudio.paInt16
        self.RATE = RATE

    def is_silent(self, snd_data):
        # Returns 'True' if below the 'silent' threshold
        return max(snd_data) < self.THRESHOLD

    def normalize(self, snd_data):
        # Average the volume out
        MAXIMUM = 16384
        times = float(MAXIMUM) / max(abs(i) for i in snd_data)
        r = array('h')
        for i in snd_data:
            r.append(int(i * times))
        return r

    def trim(self, snd_data):
        # Trim the blank spots at the start and end
        def _trim(snd_data_):
            snd_started = False
            r = array('h')
            for i in snd_data_:
                if not snd_started and abs(i) > self.THRESHOLD:
                    snd_started = True
                    r.append(i)
                elif snd_started:
                    r.append(i)
            return r

        # Trim to the left
        snd_data = _trim(snd_data)

        # Trim to the right
        snd_data.reverse()
        snd_data = _trim(snd_data)
        snd_data.reverse()
        return snd_data

    def add_silence(self, snd_data, seconds):
        # Add silence to the start and end of 'snd_data' of length 'seconds' (float)
        silence = [0] * int(seconds * self.RATE)
        r = array('h', silence)
        r.extend(snd_data)
        r.extend(silence)
        return r

    def record(self):
        """
        Record a word or words from the microphone and
        return the data as an array of signed shorts.

        Normalizes the audio, trims silence from the
        start and end, and pads with 0.5 seconds of
        blank sound to make sure VLC et al can play
        it without getting chopped off.
        """
        p = pyaudio.PyAudio()
        stream = p.open(format=self.FORMAT, channels=1, rate=self.RATE,
                        input=True, output=True,
                        frames_per_buffer=self.CHUNK_SIZE)

        num_silent = 0
        snd_started = False

        r = array('h')

        i = 0
        while i < 5000:
            i += 1
            # print(f"{i}")
            # little endian, signed short
            snd_data = array('h', stream.read(self.CHUNK_SIZE))
            if byteorder == 'big':
                snd_data.byteswap()
            r.extend(snd_data)

            silent = self.is_silent(snd_data)

            if silent and snd_started:
                num_silent += 1
            elif not silent and not snd_started:
                snd_started = True

            if snd_started and num_silent > 30:
                break

        sample_width = p.get_sample_size(self.FORMAT)
        stream.stop_stream()
        stream.close()
        p.terminate()

        r = self.normalize(r)
        r = self.trim(r)
        r = self.add_silence(r, 0.5)
        return sample_width, r

    def record_to_file(self, path):
        # Records from the microphone and outputs the resulting data to 'path'
        print("Recording....")
        sample_width, data = self.record()
        data = pack('<' + ('h' * len(data)), *data)
        recordTime = float(len(data)) / self.RATE
        print(f"{recordTime:.2f} seconds recorded")
        #
        time.sleep(1)
        #
        wf = wave.open(path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(self.RATE)
        wf.writeframes(data)
        wf.close()
        #
        return recordTime


class RachelUI(QDialog, Ui_read_text):
    def __init__(self, read_text_):
        super(RachelUI, self).__init__()
        self.setupUi(read_text_)
        self.engine = pyttsx3.init()
        # Parameters
        self.rate = self.engine.getProperty('rate')
        self.set_read_speed()
        self.audioFilename = "demo.wav"
        self.audioFilenameLast = self.audioFilename
        self.leAudioFilename.setText(self.audioFilename)
        self.p = None
        # Click/Trigger Actions
        self.pbRead.clicked.connect(self.read_text)
        self.pbSlower.clicked.connect(self.read_slower)
        self.pbFaster.clicked.connect(self.read_faster)
        self.pbExit.clicked.connect(self.bye_bye)
        self.pbRecord.clicked.connect(self.record)
        self.pbPlay.clicked.connect(self.play)
        self.actionOpen.triggered.connect(self.openFileNameDialog)
        self.actionExit.triggered.connect(self.bye_bye)

    def record(self):
        self.audioFilename = self.leAudioFilename.text()
        self.labelRecordStatus.setText("Recording Status: Recording.....")
        rec = Recording()
        recordingTime = rec.record_to_file(self.audioFilename)
        self.labelRecordStatus.setText(f"Recording Status: {recordingTime:.2f} seconds recorded")
        self.p = None  # Reset
        # speech recognition
        r = sr.Recognizer()
        with sr.AudioFile(self.audioFilename) as source:
            audio = r.record(source)  # read the entire audio file
        try:
            sr_text = r.recognize_google(audio)
        except sr.UnknownValueError:
            sr_text = "Google Speech Recognition could not understand what you said."
        except sr.RequestError as e:
            sr_text = "Could not request results from Google Speech Recognition service; {0}".format(e)
        self.tbSpeechToText.setText(sr_text)

    def play(self):
        self.audioFilename = self.leAudioFilename.text()
        # print(f"filenames: {self.audioFilename}, {self.leAudioFilename.text()}")
        if not path.exists(self.audioFilename) :
            print(f"Error: audio file {self.audioFilename} does not exist.")
            return
        if (self.p is None) or (self.audioFilenameLast != self.audioFilename):
            self.p = vlc.MediaPlayer(self.audioFilename)
            self.audioFilenameLast = self.audioFilename
        if self.p.get_state() == vlc.State.Playing:  # Stop playing.
            self.p.stop()
        else:  # Play
            self.p.stop()  # Stop before play
            time.sleep(1)
            self.p.play()

    # Load a text file for reading.
    def openFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "QFileDialog.getOpenFileName()", "",
                                                  "All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            with open(fileName, 'r') as f:
                lines = f.read()
            self.teText.setText(lines)

    # Slow down the read speed.
    def read_slower(self):
        self.rate -= 20
        self.set_read_speed()

    # Speed up the read speed.
    def read_faster(self):
        self.rate += 20
        self.set_read_speed()

    # Set the read speed.
    def set_read_speed(self):
        self.engine.setProperty('rate', self.rate)
        self.labelReadSpeed.setText(f"Read Speed: {self.rate} words/min")
        self.labelReadSpeed.adjustSize()

    # Read the text out loud.
    def read_text(self):
        s = self.teText.toPlainText().replace('\n', '')
        # Read the selected text only if any.
        cursor = self.teText.textCursor()
        if cursor.selectionEnd() > cursor.selectionStart():
            s = s[cursor.selectionStart():cursor.selectionEnd()]
        self.engine.say(s)
        self.engine.runAndWait()

    def bye_bye(self):
        self.engine.say("Bye Bye")
        self.engine.runAndWait()
        time.sleep(0.2)
        self.engine.stop()
        app.exit(0)


#
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    read_text = QtWidgets.QMainWindow()
    ui = RachelUI(read_text)
    read_text.show()
    sys.exit(app.exec_())
    #app.exec_()
