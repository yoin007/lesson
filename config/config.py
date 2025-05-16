# _*_ coding: utf-8 _*_
# @Time: 2024/09/23 11:31
# @Author: Tech_T

import yaml
import os


class Config:
    def __init__(self):
        self.root_path = os.path.dirname(__file__)
        self.config_path = self.root_path +'/config.yaml'

    def get_config(self, key, config_file:str = ''):
        if config_file == '':
            config_file = self.config_path
        else:
            config_file = os.path.join(self.root_path, config_file)
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config[key]

    def get_config_all(self, config_file:str = ''):
        if config_file == '':
            config_file = self.config_path
        else:
            config_file = os.path.join(self.root_path, config_file)
        with open(config_file, 'r', encoding='utf-8') as f:
            config_all = yaml.safe_load(f)
        return config_all

    def modify_config(self, key, value, config_file:str = ''):
        config_all = self.get_config_all(config_file)
        try:
            config_all[key] = value
            if config_file == '':
                config_file = self.config_path
            else:
                config_file = os.path.join(self.root_path, config_file)
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_all, f, allow_unicode=True)
                return True
        except:
            return False