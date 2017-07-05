#!flask/bin/python
from flask import Flask, request, jsonify, json
import urllib2
import requests
import subprocess
from subprocess import Popen, PIPE
from concurrent import futures
from multiprocessing import Pool, Process



# from urllib.request import urlopen
app = Flask(__name__)
with app.open_resource('json/cloud.json') as f:
    contents=json.loads(f.read())

@app.route('/chaosmonkey', methods=['GET', 'POST'])
def chaosmonkey():
    j = 0
    k = 0
    data_dict = {}
    req_url = request.json
    if req_url["hvname"] == '':
        if req_url['service'] != '':
            for i in req_url['clouds']:
                k = k + 1
            while k > j:
                with futures.ThreadPoolExecutor(max_workers=10) as executor:
                    cloudname = req_url['clouds'][j]['name']
                    servicename = req_url['service'][j]['name']
                    action = req_url['service'][j]['action']                    
                    data_dict[cloudname] = {}
                    openstack_obj = Openstack(cloudname)
                    token, tenantid = openstack_obj.getToken()
                    executor.submit(openstack_obj.serv_disable_enable,token, tenantid, servicename, action, cloudname, data_dict[cloudname])
                    j += 1
            return jsonify(data_dict)
        else:
            for i in req_url['clouds']:
                k = k + 1
                while k > j:
                    with futures.ThreadPoolExecutor(max_workers=10) as executor:
                        cloudname = req_url['clouds'][j]['name']
                        vmname = req_url['clouds'][j]['vmname']
                        action = req_url['clouds'][j]['action']
                        data_dict[cloudname]={}
                        openstack_obj = Openstack(cloudname)
                        token, tenantid = openstack_obj.getToken()
                        executor.submit(openstack_obj.vm_disable_enable,cloudname, vmname, action, token, tenantid, data_dict[cloudname])
                        j += 1
            return jsonify(data_dict)
    else:
        hvname = req_url['hvname']
        data_dict['message'] = "using IPMI to bring down the HV"
        data_dict['hypervisor'] = hvname
        return jsonify(data_dict)


class Openstack():
    cloudname = ""
    apihost = ""
    def __init__(self, cloudname):
        self.cloudname = cloudname
        self.apihost = contents['cloud'][cloudname]['apihost']

    def getToken(self):
        '''Function that returns token for keystone authentication '''
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Accept-Charset': 'utf-8'}
        user = contents['cloud'][self.cloudname]['user']
        password = contents['cloud'][self.cloudname]['password']
        url = "https://"+self.apihost+":5000/v3/auth/tokens"
        auth = {"auth": {"identity": {"methods": ["password"], "password": {
            "user": {"name": user, "domain": {"id": "default"}, "password": password}}},
                         "scope": {"project": {"name": "admin", "domain": {"id": "default"}}}}}
        r = requests.post(url, data=json.dumps(auth), headers=headers)
        output = r.json()
        token = r.headers['X-Subject-Token']
        tenantid = output['token']['project']['id']
        return token, tenantid

    def vm_disable_enable(self, cloudname, vmname, action, token, tenantid, data_dict):
        '''    Method to disable/enable one particular VM    '''
        url = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/servers/detail?all_tenants=1&limit=1&name="+vmname
        header = {'X-Auth-Token': token, 'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Accept-Charset': 'utf-8'}
        resp = requests.get(url, headers=header).json()
        for vminfo in resp["servers"]:
            vmname = vminfo["name"]
            vmid = vminfo["id"]
            url1 = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/servers/"+vmid+"/action"
            auth = {"os-"+action : "null"}
            req = requests.post(url1, data=json.dumps(auth), headers=header)
            data_dict['vmname'] = vmname
            data_dict['vmid'] = vmid
            data_dict['state'] = action

    def serv_disable_enable(self, token, tenantid, service, action, cloudname, data_dict):
        '''   Method to disable/enable one particular service based on Binary    '''
        url = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/os-services?binary="+service
        header = {'X-Auth-Token': token, 'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Accept-Charset': 'utf-8'}
        resp = requests.get(url, headers=header).json()
        host = resp['services'][1]['host']
        url1 = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/os-services/"+action
        auth = {'binary': service, 'host': host}
        req = requests.put(url1, data=json.dumps(auth), headers=header).json()
        data_dict['state'] = action
        data_dict['hypervisor'] = host
        data_dict['service'] = service

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)
