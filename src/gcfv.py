#!/usr/bin/env python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.


import pexpect


import sys
import os
import cfv

from threading import Thread

try:
    import pygtk
    pygtk.require("2.0")
except:
    pass
try:
    import gtk
    import gtk.gdk as gdk
    import gtk.glade
except:
    sys.exit(1)
    
import subprocess


class Work (Thread):
    """ GTK cfv worker thread """
    path = None
    cfvGtk = None
    def __init__(self, cfvGtk, path):
        Thread.__init__(self)
        self.cfvGtk = cfvGtk
        self.path = path

    def run(self):
        command = self.generate_command()
        self.call(command)
    
    def generate_command(self):
        dirname = self.escape(os.path.dirname(self.path))        
        pathname = self.escape(self.path)
        # TODO readd -n ?
        return "cfv -v -i -p %s --strippaths=all --progress=no --showpaths=none -f %s" % (dirname, pathname)
    
    def escape(self, path):
        path = path.replace('(','\(')
        path = path.replace(')','\)')
        path = path.replace(' ','\ ')
        return path
    
    def call(self, command):
        
        EXP_OK = '[^\r\n]+OK.\\([0-9a-f]+\\)\r\n'
        EXP_MISSING = '[^\r\n]+No such file or directory\r\n'
        EXP_CRC_FAIL = '[^\r\n]+crc does not match[^\r\n]+\r\n'
        EXP_LAST = '[^\r\n]+files[^\r\n]+\r\n'
        EXP_ANY_LINE = '[^\r\n]+\r\n'
        
        #http://www.noah.org/wiki/Pexpect#Examples
        try:
            child = pexpect.spawn (command)
            line = ' '
            done = False
            while not done:
                # We expect any of these patterns
                i = child.expect ([EXP_OK, EXP_MISSING, EXP_CRC_FAIL, EXP_LAST, EXP_ANY_LINE])
                line = child.after
                if i == 0:
                    self.update_txt(line, "darkgreen")
                if i == 1:
                    self.update_txt(line, "darkorange")
                if i == 2:
                    self.update_txt(line, "darkred")
                elif i == 3:
                    out_str = '[DONE] '+line
                    self.update_done(out_str)
                    done = True
                elif i == 4:
                    out_str = '[INFO] '+line
                    self.update_txt(out_str)
            if child.isalive():
                child.kill(0)
            child.close(force=True)
        except Exception, err:
            mesg=u"unable to execute %s" % (repr(command),)
            raise StandardError, mesg+": "+str(err)
    
    def call_cfv(self, argv):
        cfv.main(argv)
    
    def old_call(self, command):
        try:
            p = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,close_fds=True)
            child_stdout = p.stdout
             
            counter = 0
            spinnerchars=r'\|/-'
            out_str = ''
            while (p.poll()==None):
                counter += 1
                rest = counter % 4
                self.update_txt(spinnerchars[rest] + out_str)
                
#                next = child_stdout.read(1)
#                if(next):
#                    out_str += next
#                    self.update_txt(out_str)

            while True:
                next = child_stdout.readline()         # read a one-line string
                if not next:                        # or an empty string at EOF
                    break
                out_str += next 
                self.update_txt(out_str)
    
        except Exception, err:
            mesg=u"unable to execute %s" % (repr(command),)
            raise StandardError, mesg+": "+str(err)
        if (p.returncode):
            mesg=u"trouble executing %s" % (repr(command),)
            raise StandardError, mesg+": "+repr(p.returncode)
        
        
    def update_txt(self, message, color=None):
        gdk.threads_enter()
        self.cfvGtk.append_string(message, color)
        self.cfvGtk.progressbar.set_pulse_step(0.05)
        self.cfvGtk.progressbar.pulse()
        self.cfvGtk.progressbar.set_text("checking...")
        gdk.threads_leave()
        
    def update_done(self, message):
        gdk.threads_enter()
        self.cfvGtk.append_string(message)
        self.cfvGtk.progressbar.set_fraction(1.0)
        self.cfvGtk.progressbar.set_text("done")
        gdk.threads_leave()
                
        
    
    


class CfvGTK:
    """The GTK cfv frontend"""

    def __init__(self, argv):
        self.argv = argv
        
        dirname = os.path.dirname(argv[0])
        
        gladefile = os.path.join(dirname, 'gcfv.glade')
        self.wTree = gtk.glade.XML(gladefile) 
        
        dic = { 
               "on_MainWindow_destroy" : self.on_MainWindow_destroy,
               "on_MainWindow_show" :  self.on_MainWindow_show}
        self.wTree.signal_autoconnect(dic)
        
        self.textview = self.wTree.get_widget("TextView")
        self.progressbar = self.wTree.get_widget("ProgressBar")
        
        #Get the Main Window, and connect the "destroy" event
        self.window = self.wTree.get_widget("MainWindow")
        if (self.window):
        #    self.window.connect("destroy", gtk.main_quit)
            self.window.show()
        
    def on_MainWindow_destroy(self, window=None):
        gtk.main_quit()

    def on_MainWindow_show(self, event, data=None):
        #self.itemprovider.load()
        #self.append_string(self.itemprovider.curent())
        #print thread.get_ident()
        arglen = len(self.argv)
        if(arglen != 2):
            self.append_string("Expecting one argument: the file to check (got %d)" % arglen)
        else:
            file = self.argv[1]
            print "checking %s" % file
            worker = Work(self, file)
            worker.start()

    
    def append_string(self, string, color=None):
        textbuffer = self.textview.get_buffer()
        if(color):
            colorTag = textbuffer.create_tag(name=None, foreground=color)
            textbuffer.insert_with_tags(textbuffer.get_end_iter(), string, colorTag)
        else:
            textbuffer.insert(textbuffer.get_end_iter(), string)

        self.textview.scroll_mark_onscreen(textbuffer.get_insert());
        #self.textview.scroll_to_mark(textbuffer.get_insert(), 0.0)



def main(argv=None):
    if argv is None:
        argv = sys.argv
    hwg = CfvGTK(argv)
    gdk.threads_init()
    gtk.main()
    print "Bye"

if __name__ == '__main__': 
    main()  