#!/usr/bin/env python

import re
import datetime
import argparse
import sys
import yaml

from dogapi import dog_http_api as api

import pdb
pdb.set_trace()

class Alert(object):
    """
    Alert data type.
    """
    def __init__(self, alert_dict ):
        self.id = alert_dict['id']
        self.message = alert_dict['message']
        self.name = alert_dict['name']
        self.query = alert_dict['query']
        self.silenced = alert_dict['silenced']

    def __str__(self):
        return "%s" % (self.__dict__)

    def __repr__(self):
        #return dump(self.__dict__, width=2000, indent=False).rstrip('\n')
        return "%s(%r)" % (self.__class__, self.__dict__)

    def is_live(self):
        if self.id is not None:
            return True
        else:
            return False


class Alerts(object):
    """
    Collection of alerts.
    """
    def __init__(
            self,
            api_key = '89ac45815f9d2c52f57aa0fb3ab1a1c1',
            app_key = 'c3f875fd6360610ba37195adafdd1faca3737e56',
            regex_str = None
            ):

        # API creds.
        api.api_key = api_key
        api.application_key = app_key

        self.dapi = api
        self.alerts = []

    def __str__(self):
        return "%s" % (self.__dict__)

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def __len__(self):
        return len(self.alerts)

    def __iter__(self):
        return iter(self.alerts)

    def __getitem__(self, int_key):
        return self.alerts[int_key]

    def generate_yaml_string(self):
        yaml_str = '['
        for alert in self.alerts:
            alert_str = '\n'
            alert_str += yaml.dump(alert, width=9000).rstrip('\n')
            alert_str = re.sub('!!python/object:__main__.Alert ','',alert_str)
            alert_str += ','
            yaml_str += alert_str
        yaml_str = yaml_str.rstrip(',')
        yaml_str +='\n]'
        return yaml_str

    def generate_yaml_file(self, file_path='generated_alerts-'):
        # Make a time stamp to append to file.
        ts = datetime.datetime.utcnow()
        f = file_path + ts.time('%b-%d-%y-%H:%M:%S-UTC') + '.yaml'
        fp = file(f, 'w+')
        dump(self.alerts, fp)
        return f

    def read_yaml_file(self, file_path):
        fp = open(file_path, 'r')
        python_obj = yaml.load(fp)
        return python_obj

    def load_alerts_from_api(self, regex_str):
        """
        Use regex to match against the name of each alert.
        """

        # Get all the alerts from datadog.
        all_alerts = self.dapi.get_all_alerts()

        # compile regex object if regex specified.
        if regex_str is None:
            regex_str = ''
        alerts_regex = re.compile(regex_str, re.I)

        # get list of alerts I want.
        for alert in all_alerts:
            if alerts_regex.search(alert['name']):
                alert_obj = Alert(alert)
                self.alerts.append(alert_obj)

    def load_alerts_from_file(self, file_path):
        alerts_dict = self.read_yaml_file(file_path)

        for alert in alerts_dict:
            self.alerts.append(Alert(alert))

    def update_datadog(self):
        """
        Update datadog with data in self.alerts.
        """
        for alert in self.alerts:
            if alert.is_live():
                self.dapi.update_alert(alert.id, alert.name, alert.message,
                        alert.silenced)
            else:
                self.dapi.alert(alert.query, alert.name, alert.message,
                        alert.silenced)


def cmd_line(argv):
    parser = argparse.ArgumentParser(description="Manage datadog alerts")
    subparsers = parser.add_subparsers()

    # getalerts
    getalerts = subparsers.add_parser('getalerts',
            description='get alerts from datadog',
            help='get alerts from datadog')
    getalerts.add_argument('--to-file', help='Give file to write alerts too.')
    getalerts.add_argument('-r', '--regex', help='Regex string to use when selecting events.')

    # putalerts
    putalerts = subparsers.add_parser('putalerts',
            description='put alerts to datadog',
            help='put alerts to datadog')
    putalerts.add_argument('from_file', help='Use given file to create alerts.')

    args = parser.parse_args()
    return args

def getalrts(args):
    """
    method to do all the getalerts stuff.
    """
    ddogAlerts = Alerts()
    ddogAlerts.load_alerts_from_api(args.regex)

    print ddogAlerts.generate_yaml_string()

def putalrts(args):
    """
    method to do all the getalerts stuff.
    """
    ddogAlerts = Alerts()
    ddogAlerts.load_alerts_from_file(args.from_file)
    pdb.set_trace()
    ddogAlerts.update_datadog()
    print "hi"

def main():

    # Get the cmd line.
    args = cmd_line(sys.argv)

    # case/switch dictionary.
    switch = { 'getalerts': getalrts,
               'putalerts': putalrts }
    switch[sys.argv[1]](args)

    exit(0)


if __name__ == "__main__":
    main()
