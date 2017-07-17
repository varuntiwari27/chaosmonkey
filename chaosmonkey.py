#!flask/bin/python
from flask import Flask, request, jsonify, json
import urllib2
import requests
import subprocess
import collections
from subprocess import Popen, PIPE
from concurrent import futures
from multiprocessing import Pool, Process
import sqlite3
import datetime, time
import paramiko
import re



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
    # if req_url['hvname'] == '' and req_url['server'] == '':
    if req_url['hvname'] == '':
        print "no hypervisor loop"
        if req_url['clouds'][j]['service'] != '' and req_url['clouds'][j]['cpumem'] == '':
            for i in req_url['clouds']:
                print "service loop", i['name']
                k = k + 1
            print k, j
            while k > j:
                with futures.ThreadPoolExecutor(max_workers=10) as executor:
                    print "req_url is :", req_url
                    cloudname = req_url['clouds'][j]['name']
                    servicename = req_url['clouds'][j]['service']
                    action = req_url['clouds'][j]['action']   
                    data_dict[cloudname] = {}
                    # print "cloudname is :", cloudname
                    # print "service is :", servicename
                    print "this is service loop"
                    openstack_obj = Openstack(cloudname)
                    token, tenantid = openstack_obj.getToken()
                    # print "token & tenantid and cloud in service loop :", token, tenantid, cloudname
                    # print "submitting method"
                    # print token, ":", tenantid, ":", servicename, ":", cloudname
                    executor.submit(openstack_obj.service_disable_enable,token, tenantid, servicename, action, cloudname, data_dict[cloudname])
                    print "submitted method"
                    j += 1
                    print "j value is :", j
            return jsonify(data_dict)
        elif req_url['clouds'][j]['vmname'] != '' and req_url['clouds'][j]['cpumem'] == '':
            print "req_url is :", req_url
            print "vmloop"
            for i in req_url['clouds']:
                print i['name']
                k = k + 1
                print k
                while k > j:
                    with futures.ThreadPoolExecutor(max_workers=10) as executor:
                        cloudname = req_url['clouds'][j]['name']
                        vmname = req_url['clouds'][j]['vmname']
                        action = req_url['clouds'][j]['action']
                        data_dict[cloudname]={}
                        openstack_obj = Openstack(cloudname)
                        token, tenantid = openstack_obj.getToken()
                        # print "token & tenantid & cloud in vm loop :", token, tenantid, cloudname
                        executor.submit(openstack_obj.vm_disable_enable,cloudname, vmname, action, token, tenantid, data_dict[cloudname])
                        j += 1
                        # print "value of j is :", j 
            return jsonify(data_dict)
        elif req_url['clouds'][j]['cpumem'] != '' and req_url['clouds'][j]['vmname'] == '':
            print "req_url is :", req_url
            print "cpumem loop"
            for i in req_url['clouds']:
                print i['name']
                k = k + 1
                print k
                while k > j:
                    with futures.ThreadPoolExecutor(max_workers=10) as executor:
                        cloudname = req_url['clouds'][j]['name']
                        servicename = req_url['clouds'][j]['service']
                        flag = req_url['clouds'][j]['cpumem']
                        data_dict[cloudname]={}
                        openstack_obj = Openstack(cloudname)
                        token, tenantid = openstack_obj.getToken()
                        # print "token & tenantid & cloud in cpumem loop :", token, tenantid, cloudname
                        executor.submit(openstack_obj.cpu_mem,cloudname, token, tenantid, servicename, flag, data_dict[cloudname])
                        j += 1
                        # print "value of j is :", j 
            # print ssh_stdin, ssh_stdout, ssh_stderr
            return jsonify(data_dict)
    else:
        print "elif loop"
        print "req_url is :", req_url
        hvname = req_url['hvname']
        now = datetime.datetime.now()
        message = "using IPMI to bring down the HV for chaosmonkey testing"
        state = "down"
        data_dict['message'] = message
        data_dict['hypervisor'] = hvname
        data_dict['state'] = state
        data_dict['time'] = now
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        # sql = 'INSERT INTO hv_info VALUES (?,?,?,?)',(hvname,state,now,message)
        # print sql
        # c.execute(sql)
        c.execute("INSERT INTO hv_info VALUES (?,?,?,?)", (hvname,state,now,message))
        conn.commit()
        conn.close()
        return jsonify(data_dict)



class Openstack():
    cloudname = ""
    apihost = ""
    vmname = ""
    service = ""
    flag = ""
    action = ""
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
        # print "token id is :", token
        # print "project id is :", tenantid
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
            print vmname, vmid
            url1 = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/servers/"+vmid+"/action"
            auth = {"os-"+action : "null"}
            req = requests.post(url1, data=json.dumps(auth), headers=header)
            now = datetime.datetime.now()
            data_dict['vmname'] = vmname
            data_dict['vmid'] = vmid
            data_dict['state'] = action
            data_dict['cloud'] = cloudname
            data_dict['time'] = now
            conn = sqlite3.connect("/Users/vktiwar/service.db")
            '''  Insert the response values in DB for future refernce '''
            c = conn.cursor()
            c.execute("INSERT INTO vm_info VALUES (?,?,?,?,?)", (cloudname,vmname,vmid,action,now))
            print "inserted"
            conn.commit()
            conn.close()
            print "sqlite completed"


    def service_disable_enable(self, token, tenantid, service, action, cloudname, data_dict):
        '''   Method to disable/enable one particular service based on Binary    '''
        url = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/os-services?binary="+service
        # print "url :", url
        # print "cloudname:", cloudname, "token:", token, "tenantid:", tenantid, "service:", service
        header = {'X-Auth-Token': token, 'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Accept-Charset': 'utf-8'}
        resp = requests.get(url, headers=header).json()
        host = resp['services'][1]['host']
        print "value of host :", host
        url1 = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/os-services/"+action
        auth = {'binary': service, 'host': host}
        req = requests.put(url1, data=json.dumps(auth), headers=header).json()
        # print "url1 :", url1
        # print "the service json is:", req
        now = datetime.datetime.now()
        # print " Current time is :", now
        data_dict['state'] = action
        data_dict['hypervisor'] = host
        data_dict['service'] = service
        data_dict['cloud'] = cloudname
        data_dict['time'] = now
        '''  Insert the response values in DB for future refernce '''
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        c.execute("INSERT INTO serv_info VALUES (?,?,?,?,?)", (cloudname,host,service,action,now))
        print "inserted"
        conn.commit()
        conn.close()
        print "sqlite completed"

    def cpu_mem(self, cloudname, token, tenantid, service, flag, data_dict):
        ''' Method to intoduce high CPU/MEM usage on random hypervisors '''
        url = "https://"+self.apihost+":8774/v2.1/"+tenantid+"/os-services?binary="+service
        # print "url :", url
        # print "cloudname:", cloudname, "token:", token, "tenantid:", tenantid, "service:", service
        header = {'X-Auth-Token': token, 'Content-Type': 'application/json', 'Accept': 'application/json',
                  'Accept-Charset': 'utf-8'}
        # print "after header", header
        resp = requests.get(url, headers=header).json()
        now = datetime.datetime.now()
        # print "after resp"
        # print "response is :", resp
        host = resp['services'][1]['host']
        print "value of host :", host
        if flag == 'cpu':
            chaos_type = flag
            print "chaos_type is :", flag
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username="****", password="****")
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("sudo apt install stress-ng | egrep -vi 'installed|remove|password|version|reading|building|lib*|timelimit|qemu|python' \n stress-ng --cpu 8 --io 16 --vm 2 --vm-bytes 4096 --fork 4 --timeout 10s --metrics-brief | egrep -vi 'warning|dispatching|successful|default'", get_pty=True)
            # ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("uptime", get_pty=True)
            ssh_stdin.write('*\n')
            ssh_stdin.flush()
            output = ssh_stdout.read()
            error = ssh_stderr.readlines()
            raw = re.sub(".*WARNING.*\n?|.*password.*\n?", "", output).replace('\r','').replace('stress-ng:','').replace('info:','')
            string = re.sub(r'\[.+?\]\s*','',raw)
            # print "l is :", string
            formattedstring = re.split("\n+", string)
            formattedstring.remove('')
            formattedstring.remove('')
            new_string = json.dumps(formattedstring)
            data_dict['chaos_type'] = chaos_type
            data_dict['cloud'] = cloudname
            data_dict['host'] = host
            data_dict['report'] = formattedstring
            data_dict['time'] = now
            print "formatted string: ", new_string
            '''  Insert the response values in DB for future refernce '''
            conn = sqlite3.connect("/Users/vktiwar/service.db")
            c = conn.cursor()
            print "connection established", chaos_type,cloudname,host,new_string,now
            c.execute("INSERT INTO chaos_info VALUES (?,?,?,?,?)", (chaos_type,cloudname,host,new_string,now))
            print "inserted"
            conn.commit()
            conn.close()
            print "sqlite completed"
        else:
            chaos_type = flag
            print "chaos_type is :", chaos_type
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username="****", password="****")
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("sudo apt install stress-ng | egrep -vi 'installed|remove|password|version|reading|building|lib*|timelimit|qemu|python' \n stress-ng -m 2 --timeout 10s --metrics-brief | grep 'stress-ng' | egrep -vi 'warning|dispatching|successful|default'", get_pty=True)
            # ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("uptime", get_pty=True)
            ssh_stdin.write('****\n')
            ssh_stdin.flush()
            output = ssh_stdout.read()
            error = ssh_stderr.readlines()
            raw = re.sub(".*WARNING.*\n?|.*password.*\n?", "", output).replace('\r','').replace('stress-ng:','').replace('info:','')
            string = re.sub(r'\[.+?\]\s*','',raw)
            formattedstring = re.split("\n+", string)
            formattedstring.remove('')
            formattedstring.remove('')
            new_string = json.dumps(formattedstring)
            print "new_string :", new_string
            data_dict['chaos_type'] = chaos_type
            data_dict['cloud'] = cloudname
            data_dict['host'] = host
            data_dict['report'] = formattedstring
            data_dict['time'] = now
            '''  Insert the response values in DB for future refernce '''
            conn = sqlite3.connect("/Users/vktiwar/service.db")
            c = conn.cursor()
            print "connection established", chaos_type,cloudname,host,new_string,now
            c.execute("INSERT INTO chaos_info VALUES (?,?,?,?,?)", (chaos_type,cloudname,host,new_string,now))
            print "inserted"
            conn.commit()
            conn.close()
            print "sqlite completed"




@app.route('/vmreport', methods=['GET'])
def vmreport():
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        sql = "SELECT * FROM vm_info"
        c.execute(sql)
        # c.execute("SELECT * FROM vm_info")
        print "start"
        report = c.fetchall()
        print "sqlite completed"
        vm_list = []
        for row in report :
            d = collections.OrderedDict()
            d['cloudname'] = row[0]
            d['vmname'] = row[1]
            d['vmid'] = row[2]
            d['action'] = row[3]
            d['time'] = row[4]
            vm_list.append(d)
        return jsonify(vm_list)
        conn.close()


@app.route('/hvreport', methods=['GET'])
def hvreport():
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        sql = "SELECT * FROM serv_info"
        c.execute(sql)
        print "start"
        report = c.fetchall()
        print c.fetchall()
        print "sqlite completed"
        hv_list = []
        for row in report :
            d = collections.OrderedDict()
            d['cloudname'] = row[0]
            d['host'] = row[1]
            d['service'] = row[2]
            d['action'] = row[3]
            d['time'] = row[4]
            hv_list.append(d)
        return jsonify(hv_list)
        conn.close()

@app.route('/hwreport', methods=['GET'])
def hwreport():
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        sql = "SELECT * FROM hv_info"
        c.execute(sql)
        print "start"
        report = c.fetchall()
        print c.fetchall()
        print "sqlite completed"
        hw_list = []
        for row in report :
            d = collections.OrderedDict()
            d['host'] = row[0]
            d['state'] = row[1]
            d['time'] = row[2]
            d['message'] = row[3]
            hw_list.append(d)
        return jsonify(hw_list)
        conn.close()

@app.route('/chaosreport', methods=['GET'])
def chaosreport():
        conn = sqlite3.connect("/Users/vktiwar/service.db")
        c = conn.cursor()
        sql = "SELECT * FROM chaos_info"
        c.execute(sql)
        print "start"
        report = c.fetchall()
        print c.fetchall()
        print "sqlite completed"
        hw_list = []
        for row in report :
            d = collections.OrderedDict()
            d['host'] = row[0]
            d['state'] = row[1]
            d['time'] = row[2]
            d['message'] = row[3]
            hw_list.append(d)
        return jsonify(hw_list)
        conn.close()



if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)
