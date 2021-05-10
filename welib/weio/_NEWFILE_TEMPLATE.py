import numpy as np
import pandas as pd
import os

try:
    from .file import File, WrongFormatError, BrokenFormatError
except:
    EmptyFileError    = type('EmptyFileError', (Exception,),{})
    WrongFormatError  = type('WrongFormatError', (Exception,),{})
    BrokenFormatError = type('BrokenFormatError', (Exception,),{})
    File=dict

class XXXFile(File):

    @staticmethod
    def defaultExtensions():
        return ['.XXX']

    @staticmethod
    def formatName():
        return 'XXX file'

    def __init__(self,filename=None,**kwargs):
        self.filename = filename
        if filename:
            self.read(**kwargs)

    def read(self, filename=None, **kwargs):
        """ read self, or read filename if provided """
        if filename:
            self.filename = filename
        if not self.filename:
            raise Exception('No filename provided')
        if not os.path.isfile(self.filename):
            raise OSError(2,'File not found:',self.filename)
        if os.stat(self.filename).st_size == 0:
            raise EmptyFileError('File is empty:',self.filename)
        # Calling children function
        self._read(**kwargs)

    def write(self, filename=None):
        """ write self, or to filename if provided """
        if filename:
            self.filename = filename
        if not self.filename:
            raise Exception('No filename provided')
        # Calling children function
        self._write()

    def _read(self):
        """ """
        self.data=[]
        with open(self.filename, 'r', errors="surrogateescape") as f:
            for i, line in enumerate(f):
                data.append(line)

    def _write(self):
        """ """
        with open(self.filename,'w') as f:
            f.write(self.toString)

    def toDataFrame(self):
        #cols=['Alpha_[deg]','Cl_[-]','Cd_[-]','Cm_[-]']
        #dfs[name] = pd.DataFrame(data=..., columns=cols)
        #df=pd.DataFrame(data=,columns=)
        return 


    def toString(self):
        s=''
        return s

    def __repr__(self):
        s ='Class XXXX (attributes: data)\n'
        return s


