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
import json
import ConfigParser

from dogapi import dog_http_api as api

import pdb


class DataDogObject(object):
    def __repr__(self):
        #return json.dumps(self.__dict__)
        return json.dumps(self.__dict__, indent=4)

    def __return_dict__(self):
        return self.__dict__

    def to_json(self):
        return json.dumps(self.__dict__, indent=4)

    def to_yaml(self):
        return yaml.dumps(self.__return_dict__())

    def is_live(self):
        """
        Determines if a specific alert is already in datadog.
        """
        #pdb.set_trace()
        if (self.id != 0):
            return True
        else:
            return False


class DataDogObjectCollection(object):
    def __init__(self, api_key=None, app_key=None, config_file=None):
        """
        Get credentials and setup api.
        """
        api.api_key, api.application_key = self.__return_credentials__(api_key, app_key, config_file)
        self.dapi = api

        """
        Holds data.  Holds alerts.
        """
        self.data = []

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

        return "%s" % (self.__dict__)

        return "%s(%r)" % (self.__class__, self.__dict__)

    def __repr__(self):
        return json.dumps(self.__dict__, indent=4)

    def __return_dict__(self):
        return self.__dict__

    def to_json(self):
        return json.dumps(self.__dict__, indent=4)

    def to_yaml(self):
        string = json.dumps(self.data)
        return yaml.load(string)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, int_key):
        return self.data[int_key]

    def return_id(self, int_id):
        for obj in self.data:
            if obj.id == int_id:
                return obj
        return None

    def generate_yaml_from_data(self):
        """
        Method iterates through self.data and constructs a yaml string
        from all items.  yaml string is an array of hashes.
        """
        yaml_str = '['
        for alert in self.data:
            alert_str = '\n'
            alert_str += yaml.dump(alert, width=9000).rstrip('\n')
            alert_str = re.sub('!!python/object:__main__.\s+', '', alert_str)
            alert_str += ','
            yaml_str += alert_str
        yaml_str = yaml_str.rstrip(',')
        yaml_str += '\n]'
        return yaml_str

    def generate_json_from_data(self):
        return self.data

    def do(self, args):
        switch = {'get': self.get,
                  'put': self.put}
        switch[args.sub_subparser_name](args)

    def get(self, args):
        self.load_data_from_api(args.regex)
        #pdb.set_trace()

        if args.get_id != 0:
            data = []
            data.append(self.return_id(args.get_id))
        else:
            data = self.generate_json_from_data()
        print data

    def put(self, args):
        self.load_data_from_file(args.from_file)
        self.update_datadog()


class Alert(DataDogObject):
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


class Alerts(DataDogObjectCollection):
    """
    Collection of alerts.
    """

    def load_data_from_api(self, regex_str):
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
                self.data.append(alert_obj)

    def load_data_from_file(self, file_path):
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
            self.data.append(Alert(alert_dict))

    def update_datadog(self):
        """
        Update datadog with data in self.data.
        To create a new alert:  Leave the id attribute None.  This will create a new alert.
        To update the alert:  id must have a valid positive integer that maps to a current event.
        To delet an event: make the id a negative number.  This will delete the alert.
        """
        for alert in self.data:
            if alert.is_live():
                if alert.id < 0:
                    self.dapi.delete_alert(abs(alert.id))
                else:
                    self.dapi.update_alert(alert.id, alert.query, alert.name, alert.message, alert.silenced)
            else:
                self.dapi.alert(alert.query, alert.name, alert.message, alert.silenced)


class Dashbrd(DataDogObject):
    """
    """
    def __init__(self, dash_dict):
        self.id = dash_dict['id']
        self.title = dash_dict['title']
        self.description = dash_dict['description']
        self.graphs = dash_dict['graphs']


class Dashbrds(DataDogObjectCollection):

    def load_data_from_api(self, regex_str):
        """
        Usese datadog method get_all_alerts to get all alerts.
        If regex_str is specified then regex is applied to 'name' field for each alert.
        Otherwise regex_str = '' and will match every alert.
        """

        # Get all the alerts from datadog.
        all_dashboards = self.dapi.dashboards()
        #pdb.set_trace()

        # compile regex object if regex specified.
        if regex_str is None:
            regex_str = ''
        dash_regex = re.compile(regex_str, re.I)

        # get list of alerts I want.
        for dash in all_dashboards:
            if dash_regex.search(dash['title']):
                obj = self.dapi.dashboard(dash['id'])
                dash_obj = Dashbrd(obj)
                self.data.append(dash_obj)

    def load_data_from_file(self, file_path):
        fp = open(file_path, 'r')
        data_python_obj = json.load(fp)

        for data_dict in data_python_obj:
            self.data.append(Dashbrd(data_dict))

    def update_datadog(self):
        """
        Update datadog with data in self.data.
        To create a new alert:  Leave the id attribute None.  This will create a new alert.
        To update the alert:  id must have a valid positive integer that maps to a current event.
        To delet an event: make the id a negative number.  This will delete the alert.
        """
        for obj in self.data:
            if obj.is_live():
                if obj.id < 0:
                    self.dapi.delete_dashboard(abs(obj.id))
                else:
                    self.dapi.update_dashboard(obj.id, obj.title, obj.description, obj.graphs)
            else:
                self.dapi.create_dashboard(obj.title, obj.description, obj.graphs)

        return self.data


def cmd_line(argv):
    """
    Get the command line arguments and options.
    """
    parser = argparse.ArgumentParser(description="Manage datadog alerts")
    parser.add_argument('-c', '--config', default='/etc/dd-agent/datadog.conf',
            help='Specify datadog config file to get api key info.')
    parser.add_argument('--api-key', default=None, help='Specify API key.')
    parser.add_argument('--app-key', default=None, help='Specify APP key.')
    parser.add_argument('-y', '--use-yaml', action='store_true', default=False, help='All output/input will use yaml.')
    subparsers = parser.add_subparsers(dest='subparser_name')

    # Parent parser
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-i', '--get-id', type=int, default=0)
    parent_parser.add_argument('-r', '--regex', help='Regex string to use when selecting events.')

    # alerts
    alerts = subparsers.add_parser('alerts',
            description='Manage DataDog alerts.', help='Manage DataDog alerts.')
    alert_sub = alerts.add_subparsers(dest='sub_subparser_name')
    alert_get = alert_sub.add_parser('get',
            description='Gets the alerts from datadog and prints them to stdout.', help='get alerts from datadog',
            parents=[parent_parser])
    alert_put = alert_sub.add_parser('put',
            description='Takes alerts from file argument and puts them in datadog.', help='put alerts to datadog')
    alert_put.add_argument('from_file', help='Use given file to create alerts. REQUIRED')

    # dashboards
    dash = subparsers.add_parser('dashboards',
            description='Manage dadadog dashboards.', help='Manage datadog dashboards.')
    dash_sub = dash.add_subparsers(dest='sub_subparser_name')
    dash_get = dash_sub.add_parser('get',
            description='Get dashboards from datadog.', help='Get dashboards from datadog.',
            parents=[parent_parser])
    dash_put = dash_sub.add_parser('put',
            description='Put dashboards to datadog.', help='Put dashboards to datadog.')
    dash_put.add_argument('from_file', help='Use given file to create alerts. REQUIRED')

    args = parser.parse_args()
    return args


def alert_ops(args):
    """
    Gets the alerts from datadog and prints them to stdout.
    """
    ddogAlerts = Alerts(args.api_key, args.app_key, args.config)
    ddogAlerts.do(args)


def dash_ops(args):
    """
    dashboard operations.
    """
    ddogDashbrds = Dashbrds(args.api_key, args.app_key, args.config)
    ddogDashbrds.do(args)


def main():
    """
    Main function where it all comes together.
    """
    # Get the cmd line.
    args = cmd_line(sys.argv)

    # case/switch dictionary.
    switch = {'alerts': alert_ops,
              'alerts': alert_ops,
              'dashboards': dash_ops}
    switch[args.subparser_name](args)

    exit(0)


if __name__ == "__main__":
    main()
