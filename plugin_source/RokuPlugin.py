"""

#############################################

#   Roku Deploy Plugin for Sublime Text 3   #

#############################################

# Simple plugin for deploying developers    #

# channels to Roku boxes.                   #

# version: 1.0.0                            #

#############################################

"""

import sublime, sublime_plugin
import os, sys
import zipfile
import time
import json
import re
import RokuPlugin.requestsExternalModule


class RokuDeployCommand(sublime_plugin.WindowCommand):

    def run(self):
        print('\n'*20)
        print ("================================")
        print (time.ctime())
        self.view               = self.window.active_view()
        self.requests           = RokuPlugin.requestsExternalModule
        self.HTTPDigestAuth     = self.requests.auth.HTTPDigestAuth

        self.config             = sublime.load_settings("RokuPlugin.sublime-settings")

        self.boxIpAddress       = self.config.get("rokuIp")
        self.rokuDevUsername    = self.config.get("rokuDevUsername")
        self.rokuDevPass        = self.config.get("rokuDevPass")
        self.timeOut            = self.config.get("timeOut")
        self.zipExcludeRegex    = self.getExcludeRegex()

        if self.checkRokuDevTarget():
            archivePath = self.getArchivePath()
            self.createZipArchive(archivePath)

            if os.path.isfile(archivePath) :
                print("Created - " + archivePath)
                response = self.installChannel(archivePath)
                try:
                    print("response - ", response.status_code, response.headers)
                except AttributeError:
                    print()

        print ("================================")



    def checkRokuDevTarget(self):
        result = True
        additionalParams = {
            "timeout" : self.timeOut
        }

        # check ECP, to verify we are talking to a Roku
        response = self.performRequest("get", "http://" + self.boxIpAddress + ":8060", additionalParams)
        if response == None or "Roku" not in response.headers["server"]:
            print("ERROR: Device is not responding to ECP...is it a Roku?")
            result = False

        # check dev web server.
        # Note, it should return 401 Unauthorized since we aren't passing the password.
        response = self.performRequest("get", "http://" + self.boxIpAddress)
        if response == None or response.status_code != self.requests.codes.unauthorized:
            print("ERROR: Device server is not responding...is the developer installer enabled?", additionalParams)
            result = False

        return result

    def createZipArchive(self, archivePath):
        projectRoot = self.getProjectRoot()
        print("projectRoot -", projectRoot)
        print("archivePath -", archivePath)

        zf = zipfile.ZipFile(archivePath, "w", zipfile.ZIP_DEFLATED)

        for dirname, subdirs, files in os.walk(projectRoot):
            for filename in files:
                absname = os.path.abspath(os.path.join(dirname, filename))
                if self.isFileNeeded(absname):
                    arcname = absname[len(projectRoot) + 1:]
                    zf.write(absname, arcname)

        zf.close()

    def installChannel(self, archivePath):
        self.goHome()
        self.goHome()

        data = {"mysubmit": "Replace"}
        archive = open(archivePath, "rb")
        files = {"archive": archive}

        additionalParams = {
            "auth" : self.getAuthObject(),
            "data" : data,
            "files" : files,
            "timeout" : self.timeOut
        }

        host = "http://" + self.boxIpAddress + "/plugin_install"
        if os.name == 'nt':
            response = self.performRequest("post", "http://" + self.boxIpAddress + "/plugin_install", additionalParams=additionalParams)
        else:
            curlParam =  ' --user '+ self.rokuDevUsername+":"+self.rokuDevPass + ' --digest --silent --show-error -F "mysubmit=Install" -F "archive=@'+archivePath+'" --output /tmp/dev_server_out --write-out "%{http_code}" '+host
            response = os.system('curl'+curlParam)

        archive.close()

        return response

    def goHome(self):
        additionalParams = {
            "timeout" : self.timeOut
        }

        response = self.performRequest("post", "http://" + self.boxIpAddress + ":8060/keypress/Home", additionalParams=additionalParams)

        return response

    def performRequest(self, method, url, additionalParams = {}):
        response = None

        auth = additionalParams.get("auth", None)
        data = additionalParams.get("data", None)
        json = additionalParams.get("json", None)
        files = additionalParams.get("files", None)
        timeout = additionalParams.get("timeout", None)

        requestFunction = getattr(self.requests, method, None)
        if requestFunction != None:
            try:
                response = requestFunction(url, auth=auth, data=data, json=json, files=files, timeout=timeout)
                print("request - ", response.request.url, response.request.headers)
            except Exception as e:
                print(str(e))

        return response

    def getProjectRoot(self):
        projectRoot = ""
        pathPair = os.path.split(self.view.file_name())
        while not self.isValid(pathPair[1]):
            pathPair = os.path.split(pathPair[0])

        if pathPair[1] != '':
            projectRoot = pathPair[0]

        return projectRoot

    def isValid(self, fileName):
        res = False
        if 'manifest' in fileName:
            res = True
        elif 'components' in fileName:
            res = True
        elif 'source' in fileName:
            res = True
        elif fileName == '':
            res = True

        return res

    def getArchivePath(self):
        projectRoot = self.getProjectRoot()
        archiveRoot = os.path.join(projectRoot, "out")

        if os.path.isdir(archiveRoot) == False:
            os.mkdir(archiveRoot)

        archivePath = os.path.join(archiveRoot, "channel.zip")

        return archivePath

    def getAuthObject(self):
        return self.HTTPDigestAuth(self.rokuDevUsername, self.rokuDevPass)

    def getExcludeRegex(self):
        regexString = ""

        for item in self.config.get("zipExclude"):
            regexString = regexString + item + "|"

        regexString = regexString[:-1]

        return re.compile(regexString)

    def isFileNeeded(self, filePath):
        result = False

        if self.zipExcludeRegex.search(filePath) == None:
            result = True

        return result

