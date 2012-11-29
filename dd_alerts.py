#!/usr/bin/env python
"""
This script is kind of a 'cloud formation' for setting up datadog alerts.  There are two main subcommands, getalerts and putalerts.
Getalerts will get live alerts from datadog and output their descriptions to stdout as a yaml string.  Putalerts will take a yaml file
as input and either create new alerts or update current ones.
"""

import re
import argparse
import sys
import os
import yaml
import ConfigParser

from dogapi import dog_http_api as api

import pdb


class Alert(object):
    """
    Alert data type.  Holds data for specific alerts.
    """
    def __init__(self, alert_dict):
        """
        alert_dict must have the following:
            alert_dict['id']:       Integer.  The id of the alert.  This is None on new alert creation.
            alert_dict['message']:  String.  Describes how alert will inform of problem (ie. pagerduty)
            alert_dict['name']:     String.  The name description of the alert.
            alert_dict['query']:    String.  The guts of the alert.  See the docs on the datadog alert api for more info.
            alert_dict['silenced']: Boolean.  Mute or not.
        """
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
        """
        Determines if a specific alert is already in datadog.
        """
        if self.id is not None:
            return True
        else:
            return False


class Alerts(object):
    """
    Collection of alerts.
    """
    def __init__(self, api_key=None, app_key=None, config_file=None):
        """
        Get credentials and setup api.
        """
        api.api_key, api.application_key = self.__return_credentials__(api_key, app_key, config_file)
        self.dapi = api

        """
        Holds data.  Holds alerts.
        """
        self.alerts = []

    def __return_credentials__(self, api_key, app_key, config_file):
        """
        Determines datadog credentials.
        Api credentials are held here.  They are needed for the
        load_alerts_from_api() and update_datadog() methods.
        1.  Use the values supplied at instantiation.
        2.  If None, see the config file.  self.config_file =  <input values> || '/etc/dd-agent/datadog.conf'
        """

        """
        If both api_key and app_key are not None then return their values.
        """
        if ((api_key and app_key) is not None):
            return api_key, app_key

        """
        Fail if config_file is None or if the path is not legit.
        """
        if (config_file is None) or (os.path.isfile(config_file) == False):
            raise Exception('Do not have a valid config file!!!!!!')

        """
        At this point the value of config_file is valid.  So parse it.
        """
        #pdb.set_trace()
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        api_key = config.get('Main', 'api_key')
        app_key = config.get('Main', 'application_key')
        #pdb.set_trace()

        """
        Make sure we got good values.
        """
        if (api_key == '') or (app_key == ''):
            raise Exception('Bad values!!!!')

        """
        Everything looks good!
        """
        return api_key, app_key

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

    def generate_yaml_from_data(self):
        """
        Method iterates through self.alerts and constructs a yaml string
        from all items.  yaml string is an array of hashes.
        """
        yaml_str = '['
        for alert in self.alerts:
            alert_str = '\n'
            alert_str += yaml.dump(alert, width=9000).rstrip('\n')
            alert_str = re.sub('!!python/object:__main__.Alert ', '', alert_str)
            alert_str += ','
            yaml_str += alert_str
        yaml_str = yaml_str.rstrip(',')
        yaml_str += '\n]'
        return yaml_str

    def load_alerts_from_api(self, regex_str):
        """
        Usese datadog method get_all_alerts to get all alerts.
        If regex_str is specified then regex is applied to 'name' field for each alert.
        Otherwise regex_str = '' and will match every alert.
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
        """
        Loads all alerts listed in file 'file_path'.  The format of the file should be as follows:
            [
             {id: <int>, message: <string>, name: <string>, query: <string>, silenced: <boolean>},
             ...
            ]
        """
        fp = open(file_path, 'r')
        alerts_python_obj = yaml.load(fp)

        for alert_dict in alerts_python_obj:
            self.alerts.append(Alert(alert_dict))

    def update_datadog(self):
        """
        Update datadog with data in self.alerts.
        To create a new alert:  Leave the id attribute None.  This will create a new alert.
        To update the alert:  id must have a valid positive integer that maps to a current event.
        To delet an event: make the id a negative number.  This will delete the alert.
        """
        for alert in self.alerts:
            if alert.is_live():
                if alert.id < 0:
                    self.dapi.delete_alert(abs(alert.id))
                else:
                    self.dapi.update_alert(alert.id, alert.query, alert.name, alert.message, alert.silenced)
            else:
                self.dapi.alert(alert.query, alert.name, alert.message, alert.silenced)


def cmd_line(argv):
    """
    Get the command line arguments and options.
    """
    parser = argparse.ArgumentParser(description="Manage datadog alerts")
    parser.add_argument('-c', '--config', default='/etc/dd-agent/datadog.conf',
            help='Specify datadog config file to get api key info.')
    parser.add_argument('--api-key', default=None, help='Specify API key.')
    parser.add_argument('--app-key', default=None, help='Specify APP key.')
    subparsers = parser.add_subparsers(dest='subparser_name')

    # getalerts
    getalerts = subparsers.add_parser('getalerts',
            description='Gets the alerts from datadog and prints them to stdout.',
            help='get alerts from datadog')
    getalerts.add_argument('-r', '--regex', help='Regex string to use when selecting events.')

    # putalerts
    putalerts = subparsers.add_parser('putalerts',
            description='Takes alerts from file argument and puts them in datadog.',
            help='put alerts to datadog')
    putalerts.add_argument('from_file', help='Use given file to create alerts. REQUIRED')

    args = parser.parse_args()
    return args


def getalrts(args):
    """
    Gets the alerts from datadog and prints them to stdout.
    """
    ddogAlerts = Alerts(args.api_key, args.app_key, args.config)
    ddogAlerts.load_alerts_from_api(args.regex)
    print ddogAlerts.generate_yaml_from_data()


def putalrts(args):
    """
    Takes alerts from file argument and puts them in datadog.
    """
    ddogAlerts = Alerts(args.api_key, args.app_key, args.config)
    ddogAlerts.load_alerts_from_file(args.from_file)
    ddogAlerts.update_datadog()


def main():
    """
    Main function where it all comes together.
    """
    # Get the cmd line.
    args = cmd_line(sys.argv)

    # case/switch dictionary.
    switch = {'getalerts': getalrts,
              'putalerts': putalrts}
    switch[args.subparser_name](args)

    exit(0)


if __name__ == "__main__":
    main()
