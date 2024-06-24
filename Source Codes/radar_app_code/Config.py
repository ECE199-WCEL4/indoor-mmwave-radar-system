'''
Module:         Config.py
Author:         JP Coronado
                2020-08281
                BS Electronics Engineering
Course:         ECE 199 Capstone Project
Description:    Defines a SystemConfig object which allows for the reading and updating of
                the radar system options.
'''

import configparser
import os

class SystemConfig(configparser.ConfigParser):
    def __init__(self, filename=None, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self['SystemSettings'] = {}
        self.filename = filename
    
    def read(self):
        """
        Custom read method that checks if the file exists.
        If not, creates the file with default values.
        """
        if not os.path.exists(self.filename):
            self['SystemSettings'] = {}
            self.write_file() 
        else:
            super().read(self.filename, encoding=None)

    def write_file(self):
        """
        Write the configuration to the file.
        """
        with open(self.filename, 'w') as config_file:
            self.write(config_file)

    def clear_all_sections(self):
        for section in self.sections():
            self.remove_section(section)

    def update_config(self, on_error=None, **kwargs):
            
        for k, v in kwargs.items():
            self['SystemSettings'][k] = str(v)

        self.write_file()

        
if __name__ == "__main__":

    # Create config
    cfg = Config()
    
    # Read .ini file, if it does not exist then create file
    cfg.read('config.ini')



