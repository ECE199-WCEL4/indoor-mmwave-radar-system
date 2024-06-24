'''
Module:         MQTTClientHandler.py
Author:         JP Coronado
                2020-08281
                BS Electronics Engineering
Course:         ECE 199 Capstone Project
Description:    Defines an MQTTClientHandler object used for instantiating the MQTT client
                and storing queues for radar point data.
'''


class MQTTClientHandler:
    def __init__(self):
        self.client = None
        self.tp_proc = None
        self.radar_queues = {}
