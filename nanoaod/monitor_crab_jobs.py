#!/bin/env python3

##############################################################
# Monitor crab jobs and put the results in a summary webpage #
##############################################################

import os
import sys
import glob
import subprocess
import pexpect
import json
from datetime import datetime
import argparse


def define_css_style():
    ### define a fixed style string for the web page
    # only meant for internal use in web function

    s = '<style>'

    s += 'body {\n'
    s += 'margin: 0;\n'
    s += 'padding: 0;\n'
    s += 'width: 100%;\n'
    s += '}\n'

    s += 'h1 {\n'
    s += 'width: 100%;\n'
    s += 'text-align: center;\n'
    s += 'font-size:20px;\n'
    s += 'margin:0;\n'
    s += 'padding:0;\n'
    s += 'background: red;\n'
    s += 'color: #FFF;\n'
    s += 'display: inline-block;\n'
    s += '}\n'

    s += 'h3 {\n'
    s += 'width: 100%;\n'
    s += 'text-align: center;\n'
    s += 'font-size:15px;\n'
    s += 'background: #EAEDED;\n'
    s += 'margin:0;\n'
    s += 'padding:0;\n'
    s += 'display: inline-block;\n'
    s += '}\n'

    s += '.divide tr td { width:60%; }\n'

    # define style for progress bar, consisting of:
    # - "progress-container": the container for both the colored bars and text
    # - "progress-text": container for text overlaying the colored bars
    # - "progress-bar": the colored bar

    s += '.progress-container {\n'
    s += 'width: 100%;\n'
    s += 'height: 20px;\n'
    s += 'border: 1px solid black;\n'
    s += 'position: relative;\n'
    s += 'padding: 3px;\n'
    s += '}\n'

    s += '.progress-text {\n'
    s += 'position: absolute;\n'
    s += 'left: 5%;\n'
    s += '}\n'

    s += '.progress-bar {\n'
    s += 'position: absolute;\n'
    s += 'height: 20px;\n'
    s += '}\n'

    s += '</style>\n'

    return s


def make_progress_bar(progress_values):
    ### make html progress bar
    # input arguments:
    # - progress_values: a dict matching status names to percentages in str format,
    #   e.g. {'finished': '100%'}
    progress_str = ' '.join(['{}: {}'.format(key, val) for key, val in progress_values.items()])
    colors = {
      'finished': 'lightgreen',
      'transferring': 'turquoise',
      'running': 'deepskyblue',
      'failed': 'crimson'
    }
    html = '<td> <div class="progress-container">'
    cumul = 0
    for status, color in colors.items():
        if status not in progress_values.keys(): continue
        val = float(progress_values[status].strip('%'))
        stylestr = 'left: {}%; width: {}%; background-color: {}'.format(cumul, val, color)
        html += '<div class="progress-bar" style="{}"></div>'.format(stylestr)
        cumul += val
    html += '<div class="progress-text">'+progress_str+'</div>'
    html += '</div></td>'
    return html


def web( data, webpath, force=False ):
    ### convert sample completion info into a html document for web display.
    # input arguments:
    # - data: a dictionary as generated by the main section.
    #         it should contain the key 'samples' and optionally the key 'meta';
    #         the value for the 'meta' key is a str->str dict with meta-information
    #         to be displayed at the top of the page,
    #         the value for the 'samples' key is a dict matching sample names to status dicts.
    #         the sample names are assumed to be production/sample/version,
    #         and the status dicts are assumed to be str->str with status to fraction matching.
    #         example: data = {'samples': {
    #    'singlelepton_MC_2017_ULv5/
    #     WWG_TuneCP5_13TeV-amcatnlo-pythia8/
    #     crab_RunIISummer20UL17MiniAOD-106X_mc2017_realistic_v6-v2_singlelepton_MC_2017_ULv5': 
    #     {'running': '13.3%', 'finished': '73.3%', 'idle': '13.3%'}}}
    # - webpath: directory where the resulting index.html file should be stored.
    #            if it does not exist yet, it will be created;
    #            if it already exists and contains an index.html file, that file will be overwritten.

    # initializations
    now = datetime.now()
    if not os.path.exists(webpath): os.makedirs(webpath)

    # make the page layout and header
    page = '<html>\n'
    page += '<head>\n'+define_css_style()+'</head>\n'
    page += '<body>\n'
    page += '<table style="background-color:#2C3E50;color:#EAECEE;'
    page += 'font-size:40px;width:100%;text-align: center;">'
    page += '<tr><td>Status of ntuple production</td></tr>'
    page += '<tr><td style="font-size:15px;">Last update: '+now.strftime("%d/%m/%Y %H:%M:%S")+'</td></tr>'
    page += '</table>\n'

    # print some meta information
    page += '<div id="meta-info"><h1>Meta-info</h1></div>\n'
    if 'meta' in data.keys():
        meta = data['meta']
        for key,val in meta.items():
            page += '<table class="divide" cellpadding="5px" cellspacing="0">\n'
            page += '<tr>\n'
            page += '<td style="width:30%">'+key+'</td>'
            page += '<td style="widht:70%">'+val+'</td>\n'
            page += '</tr>\n'
        page += '</table>\n'
    else:
        page += '<table class="divide" cellpadding="5px" cellspacing="0">\n'
        page += '<tr>\n'
        page += '<td>(nothing to display)</td>'
        page += '</tr>\n'
        page += '</table>\n'

    # get the sample data
    sampledata = data['samples']

    # sort the sample list
    samples = sorted(list(sampledata.keys()),key=lambda x:x.lower())

    # loop over samples
    page += '<div id="samples"><h1>Samples</h1></div>\n'
    for sample in samples:

        # format sample name
        if sample.count('/') == 2:
            sampleparts = sample.split('/')
            samplename = sampleparts[1]
            sampleshortname = samplename.split('_')[0]
            versionname = sampleparts[2]
            versionshortname = versionname.replace('crab_','').split('-')[0]
            production = sampleparts[0]
        else:
            samplename = sample
            sampleshortname = sample
            versionname = '-'
            versionshortname = '-'
            production = '-'

        # get the grafana link for this sample
        sample_grafana = ''
        if 'grafana' in sampledata[sample].keys():
            sample_grafana = sampledata[sample]['grafana']

        # get the status data for this sample
        sample_status = sampledata[sample]['status']
        status_str = ', '.join('{}: {}'.format(key,val) 
            for key,val in sorted(sample_status.items()))
        finished_fraction = 0
        transferring_fraction = 0
        running_fraction = 0
        if 'finished' in sample_status.keys(): finished_fraction = float(sample_status['finished'].strip('%'))
        if 'transferring' in sample_status.keys(): transferring_fraction = float(sample_status['transferring'].strip('%'))
        if 'running' in sample_status.keys(): running_fraction = float(sample_status['running'].strip('%'))

        # special case for old submissions (status no longer retrievable):
        # avoid overwriting by 'finished 0%'.
        if not force:
            if( len(sample_status)==1
                and 'finished' in sample_status.keys()
                and finished_fraction == '0%' ):
                msg = 'ERROR: the status for the sample '+samplename
                msg += ' seems to be irretrievable,'
                msg += ' perhaps the submission is too long ago?'
                msg += ' Will not update the webpage to avoid overwriting useful information.'
                raise Exception(msg)

        # format the webpage entry
        page += '<table class="divide" cellpadding="5px" cellspacing="0">\n'
        page += '<tr>\n'
        # sample name
        page += '<td style="width:20%">'+sampleshortname+'</td>'
        # version name
        page += '<td style="width:20%">'+versionshortname+'</td>'
        # progress bar and text
        page += make_progress_bar(sample_status)
        # grafana link
        page += '<td style="width:20%"> <a href="'+sample_grafana+'" target="_blank">Grafana</a> </td>\n'
        page += '</tr>\n'

    page += '</table>\n'    
    page += '</body>\n'
    page += '</html>'

    wfile = open(os.path.join(webpath,'index.html'), 'w')
    wfile.write(page)
    wfile.close()


if __name__ == '__main__':

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--simpackdir', required=True, type=os.path.abspath,
      help='Simpack directory')
    parser.add_argument('-r', '--resubmit', default=False, action='store_true',
      help='Do resubmission of failed jobs (default: False, only monitor)')
    parser.add_argument('-p', '--proxy', default=None, type=os.path.abspath,
      help='Path to your proxy (default: do not export proxy explicitly)')
    parser.add_argument('-t', '--test', default=False, action='store_true',
      help='Run in test mode, process only a few samples (default: False)')
    args = parser.parse_args()
    print('Running monitor_crab_jobs.py with following configuration:')
    for arg in vars(args): print('  - {}: {}'.format(arg, getattr(args,arg)))

    # check command line arguments
    if not os.path.isdir(args.simpackdir):
        raise Exception('ERROR: simpack directory {} does not exist'.format(args.simpackdir))
    if args.proxy is not None:
        if not os.path.exists(args.proxy):
            raise Exception('ERROR: provided proxy {} does not exist'.format(args.proxy))

    # export the proxy if requested
    if args.proxy is not None:
        os.system('export X509_USER_PROXY={}'.format(args.proxy))

    # initializations
    data = {'meta': {'generating script': os.path.abspath(__file__),
            'command-line arguments': str(args)},
            'samples': {}}
    wdir = os.getcwd()

    # find all sample folders
    # (note: this is any folder inside a 'crab_logs' folder somewhere inside the simpack dir)
    fproc = sorted(glob.glob(os.path.join(args.simpackdir,'**/crab_logs/*'), recursive=True))
    nfproc = len(fproc)
    if nfproc == 0:
        msg = 'No samples found in provided simpack dir; exiting.'
        raise Exception(msg)

    # only for testing: subselect samples
    if args.test:
        ntest = min(3, nfproc)
        print('WARNING: running in test mode, will only process'
             +' {} out of {} samples'.format(ntest, nfproc))
        fproc = fproc[:ntest]

    # find the crab_status script for each sample
    # (note: cannot use standard 'crab status' command since a special container is needed)
    # (note: absolute path does not work, script must be run from inside its directory)
    cmds = []
    thisdir = os.path.abspath(os.path.dirname(__file__))
    tmpfile = os.path.join(thisdir, 'monitor_tmp_log.txt')
    for fidx, f in enumerate(fproc):
        workdir = f.split('/crab_logs/')[0]
        exe = os.path.join(workdir, 'crab_status.sh')
        if not os.path.exists(exe):
            msg = 'Could not find crab_status.sh script at location {}'.format(exe)
            msg += 'for sample {}.'.format(f)
            raise Exception(msg)
        cmd = 'cd {}'.format(workdir)
        cmd += '; bash crab_status.sh {} >> {} 2>&1'.format(f, tmpfile)
        cmds.append(cmd)

    # initialize all samples to 0% finished and empty grafana link
    for fidx, f in enumerate(fproc):
        data['samples'][os.path.basename(f)] = {'status': {'finished':'0%'}, 'grafana': ''}
        
    # loop over samples
    for fidx, f in enumerate(fproc):
        print('Now processing sample {} of {}'.format(fidx+1,len(fproc)))
        print('({})'.format(f))

        # delete previously existing log file
        if os.path.exists(tmpfile): os.system('rm {}'.format(tmpfile))

        # get appropriate command to execute
        status_cmd = cmds[fidx]
 
        # run crab status command and write the output to a log file
        success = False
        attempt = 0
        while (attempt<5 and not success):
            os.system(status_cmd)
            # check the output
            with open(tmpfile, 'r') as fin:
                outlines = fin.read().splitlines()
            thissucces = False
            if len(outlines) > 0:
                outlines = [l for l in outlines if l.startswith('Jobs status:')]
                if len(outlines) == 1: thissucces = True
            if not thissucces:
                print('Crab status seems to have failed, retrying...')
                attempt += 1
            else: success = True
        if not success:
            print('Crab status seems to have failed, skipping this sample.')
            data['samples'][os.path.basename(f)]['status'] = {'crab status': 'failed'}
            continue

        # read the log file
        jobsfailed = False
        statuscompleted = False
        with open(tmpfile, 'r') as fin:
            outlines = fin.read().splitlines()

        # remove the log file
        os.system('rm {}'.format(tmpfile))

        # parse the text from the log file
        for line in outlines:
            line = line.replace('Jobs status:','')
            words = line.split()
            if len(words)==0: continue
            # check for known job statuses
            for status in (['finished', 'running', 'transferring',
                            'failed', 'killed', 'idle','unsubmitted',
                            'toRetry']):
                if status in words[0]:
                    try: frac = words[1]
                    except: frac = '<none>'
                    # save to dict
                    data['samples'][os.path.basename(f)]['status'][status] = frac
                    # check if jobs failed for  this sample
                    if( status=='failed' ): jobsfailed = True
                    print('Percentage '+status+': '+frac)
            # find the grafana link
            if line.startswith('Dashboard monitoring URL'):
                data['samples'][os.path.basename(f)]['grafana'] = words[3]
      
        # check if job is complete
        if 'Status on the scheduler' in line:
            if 'COMPLETED' in line:
                if not os.path.isfile(f+'/results/processedLumis.json'):
                    statuscompleted = True        

        # handle case where failed jobs were found
        if jobsfailed:
            if args.resubmit:
                print('Found failed jobs, now resubmitting...')
                resubmit_cmd = status_cmd.replace('crab_status.sh', 'crab_command.sh resubmit')
                os.system(resubmit_cmd)
                print('Done')
        
        # handle case where job is complete
        if statuscompleted:
            print('This task is completed...')
                  
    # make web interface for gathered completion data              
    os.chdir(wdir)
    print('Loop over all samples completed.')
    print('Retrieved following data:')
    print(data)
    webpath = 'monitor_crab_jobs'
    web(data, webpath)
    fullpath = os.path.join(webpath, 'index.html')
    print('Sample status written to {}.'.format(fullpath))

    # print out command for downloading index.html file
    abspath = os.path.abspath(fullpath)
    user = os.getenv('USER')
    print('Use scp -r {}@lxplus.cern.ch:{} to download the results'.format(user, abspath))
    print('Done.')