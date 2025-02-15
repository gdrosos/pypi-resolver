# Copyright (c) 2018-2020 FASTEN.
#
# This file is part of FASTEN
# (see https://www.fasten-project.eu/).
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import json
import argparse
import subprocess as sp
import flask
import os
from pkginfo import Wheel, SDist, BDist
from flask import request, jsonify, make_response


TMP_DIR = "/tmp"


##### RESOLVER ######

def get_response(input_string, resolution_status, resolution_result):
    res = {"input": input_string, "status": resolution_status}
    if resolution_status:
        res['packages'] = {}
        for package, version in resolution_result:
            if package:
                res['packages'][package] = {
                    "package": package,
                    "version": version
                }
    else:
        res['error'] = resolution_result
    return res

def get_response_for_api(resolution_status, resolution_result):
    res = {}
    if resolution_status:
        list1 = []
        for package, version in resolution_result:
            if package:
                list1.append( {
                    "product": package,
                    "version": version
                })
        res = list1
    else:
        res['error'] = resolution_result
    return res

def parse_file(path):
    w = None
    package = None
    version = None
    if path.endswith(".tar.gz"):
        w = SDist(path)
    if path.endswith(".egg"):
        w = BDist(path)
    if path.endswith(".whl"):
        w = Wheel(path)
    if w:
        package = w.name
        version = w.version

    return package, version

def run_pip(input_string):
    res = set()
    pip_options = [
        "pip3", "download",
        input_string.replace("=","=="),
        "-d", TMP_DIR
    ]

    cmd = sp.Popen(pip_options, stdout=sp.PIPE, stderr=sp.STDOUT)
    stdout, _ = cmd.communicate()

    stdout = stdout.decode("utf-8").splitlines()
    err = None
    package = None
    for line in stdout:
        print (line)
        if line.startswith("ERROR"):
            err = line
            break

        fname = None
        if "Downloading" in line:
            fname = os.path.join(TMP_DIR, os.path.basename(line.split()[1]))
        elif "File was already downloaded" in line:
            fname = line.split()[4]
        if fname:
            try:
                res.add(parse_file(fname))
            except Exception as e:
                err = str(e)
                break

    if err:
        return False, err

    return True, res

###### FLASK API ######
app = flask.Flask("api")
app.config["DEBUG"] = True

@app.route('/', methods=['GET'])
def home():
    return '''<h1>PyPI Resolver</h1>
    <p>An API for resolving PyPI dependencies.</p>
    <p>API Endpoint: /dependencies/{packageName}/{version}<p>
    <p><b>Note</b>: The {version} path parameter is optional <p>
    '''


@app.errorhandler(404)
def page_not_found(e):
    return '''<h1>404</h1><p>The resource could not be found.</p>
    <p>API Endpoint: /dependencies/{packageName}/{version}<p>''', 404

@app.route('/dependencies/<packageName>', methods=['GET'])
def resolver_api_without_version(packageName):
    
    if not packageName:
        return make_response(
            jsonify({"Error": "You should provide a mandatory {packageName}"}),
            400)
    
    status, res = run_pip(packageName)

    return jsonify(get_response_for_api(status, res))

@app.route('/dependencies/<packageName>/<version>', methods=['GET'])
def resolver_api_with_version(packageName, version):
    
    if not packageName:
        return make_response(
            jsonify({"error": "You should provide `input` query parameters"}),
            400)
    
    status, res = run_pip(packageName+"="+version)

    return jsonify(get_response_for_api(status, res))

def deploy(host='0.0.0.0', port=5000):
    app.run(threaded=True, host=host, port=port)

###### CLI ######

def get_parser():
    parser = argparse.ArgumentParser(
        "Resolve dependencies of PyPI packages"
    )
    parser.add_argument(
        '-i',
        '--input',
        type=str,
        help=(
            "Input should be a string of a package name or the names of "
            "multiple packages separated by spaces. Examples: "
            "'django' or 'django=3.1.3' or 'django wagtail'"
        )
    )
    parser.add_argument(
        '-o',
        '--output-file',
        type=str,
        help="File to save the output"
    )
    parser.add_argument(
        '-f',
        '--flask',
        action='store_true',
        help="Deploy flask api"
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    input_string = args.input
    output_file = args.output_file
    cli_args = (input_string, output_file)
    flask = args.flask

    # Handle options
    if (flask and any(x for x in cli_args)):
        message = "You cannot use any other argument with --flask option."
        raise parser.error(message)
    if (not flask and not input_string):
        message = "You should always use --input option when you want to run the cli."
        raise parser.error(message)

    if flask:
        deploy()
        return
    status, res = run_pip(input_string)
    if output_file:
        with open(output_file, 'w') as outfile:
            json.dump(get_response(input_string, status, res), outfile)
    else:
        print(json.dumps(get_response(input_string, status, res)))


if __name__ == "__main__":
    main()
