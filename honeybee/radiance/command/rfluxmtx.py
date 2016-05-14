# coding=utf-8

from _commandbase import RadianceCommand
from ..datatype import RadiancePath,RadianceValue
from ..parameters.rfluxmtx import RfluxmtxParameters

import os



class Rfluxmtx(RadianceCommand):
    groundString = """
    void glow ground_glow
    0
    0
    4 1 1 1 0

    ground_glow source ground
    0
    0
    4 0 0 -1 180
    """

    skyString = """
    void glow sky_glow
    0
    0
    4 1 1 1 0

    sky_glow source sky
    0
    0
    4 0 0 1 180
    """

    class ControlParameters(object):
        def __init__(self, hemiType='u', hemiUpDirection='Y', outputFile=''):
            """Set the values for hemispheretype, hemisphere up direction
            and output file location(optional)."""
            self.hemisphereType = hemiType
            """
                The acceptable inputs for hemisphere type are:
                    u for uniform.(Usually applicable for ground).
                    kf for klems full.
                    kh for klems half.
                    kq for klems quarter.
                    rN for Reinhart - Tregenza type skies. N stands for subdivisions and defaults to 1.
                    scN for shirley-chiu subdivisions."""
            self.hemisphereUpDirection = hemiUpDirection
            """The acceptable inputs for hemisphere direction are %s""" % \
            (",".join(('X', 'Y', 'Z', 'x', 'y', 'z', '-X', '-Y',
                       '-Z', '-x', '-y', '-z')))
            self.outputFile = outputFile

        @property
        def hemisphereType(self):
            return self._hemisphereType

        @hemisphereType.setter
        def hemisphereType(self, value):
            """
                The acceptable inputs for hemisphere type are:
                    u for uniform.(Usually applicable for ground).\n
                    kf for klems full.\n
                    kh for klems half.\n
                    kq for klems quarter.\n
                    rN for Reinhart - Tregenza type skies. N stands for subdivisions and defaults to 1.\n
                    scN for shirley-chiu subdivisions."""
            if value:
                if value in ('u', 'kf', 'kh', 'kq'):
                    self._hemisphereType = value
                    return
                elif value.startswith('r'):
                    if len(value) > 1:
                        try:
                            num = int(value[1:])
                        except ValueError:
                            raise Exception(
                                "The format reinhart tregenza type skies is rN ."
                                "The value entered was %s" % value)
                    else:
                        num = ''
                    self._hemisphereType = 'r' + str(num)
                elif value.startswith('sc'):
                    if len(value) > 2:
                        try:
                            num = int(value[2:])
                        except ValueError:
                            raise Exception(
                                "The format for ShirleyChiu type values is scN."
                                "The value entered was %s" % value)
                    else:
                        raise Exception(
                            "The format for ShirleyChiu type values is scN."
                            "The value entered was %s" % value)
                    self._hemisphereType = 'sc' + str(num)
                else:
                    exceptStr = """
                    The acceptable inputs for hemisphere type are:
                        u for uniform.(Usually applicable for ground).
                        kf for klems full.
                        kh for klems half.
                        kq for klems quarter.
                        rN for Reinhart - Tregenza type skies. N stands for subdivisions and defaults to 1.
                        scN for shirley-chiu subdivisions.
                    The value entered was %s
                    """ % (value)
                    raise Exception(exceptStr)

        @property
        def hemisphereUpDirection(self):
            return self._hemisphereUpDirection

        @hemisphereUpDirection.setter
        def hemisphereUpDirection(self, value):
            """The acceptable inputs for hemisphere direction are 'X', 'Y',
            'Z', 'x', 'y', 'z', '-X', '-Y','-Z', '-x', '-y','-z'"""
            if value:
                allowedValues = ('X', 'Y', 'Z', 'x', 'y', 'z', '-X', '-Y',
                                 '-Z', '-x', '-y', '-z')
                assert value in allowedValues, "The value for hemisphereUpDirection" \
                                               "should be one of the following: %s" \
                                               % (','.join(allowedValues))

                self._hemisphereUpDirection = value

        def __str__(self):
            outputFileSpec = "o=%s" % self.outputFile if self.outputFile else ''
            return "#@rfluxmtx h=%s u=%s %s" % (self.hemisphereType,
                                                self.hemisphereUpDirection,
                                                outputFileSpec)

    class defaultSkyGround(object):
        def __init__(self, skyType=None):
            """

            Args:
                skyType: The acceptable inputs for hemisphere type are:
                    u for uniform.(Usually applicable for ground).\n
                    kf for klems full.\n
                    kh for klems half.\n
                    kq for klems quarter.\n
                    rN for Reinhart - Tregenza type skies. N stands for subdivisions and defaults to 1.\n
                    scN for shirley-chiu subdivisions."""

            self.skyType = skyType

        def __str__(self):
            skyParam = Rfluxmtx.ControlParameters(hemiType=self.skyType or 'r')
            groundParam = Rfluxmtx.ControlParameters(hemiType='u')
            groundString = Rfluxmtx.addControlParameters(Rfluxmtx.groundString,
                                                         {
                                                             'ground_glow': groundParam})
            skyString = Rfluxmtx.addControlParameters(Rfluxmtx.skyString,
                                                      {'sky_glow': skyParam})

            return groundString + '\n' + skyString

    @classmethod
    def addControlParameters(cls, inputString, modifierDict):
        if os.path.exists(inputString):
            with open(inputString)as fileString:
                fileData = fileString.read()
        else:
            fileData = inputString

        outputString = ''
        checkDict = dict.fromkeys(modifierDict.keys(), None)
        for lines in fileData.split('\n'):
            for key, value in modifierDict.items():
                if key in lines and not checkDict[
                    key] and not lines.strip().startswith('#'):
                    outputString += str(value) + '\n'
                    # outputString += lines.strip() + '\n'
                    checkDict[key] = True
            else:
                outputString += lines.strip() + '\n'

        for key, value in checkDict.items():
            assert value, "The modifier %s was not found in the string specified" % key

        if os.path.exists(inputString):
            newOutputFile = inputString + '_m'
            with open(newOutputFile, 'w')as newoutput:
                newoutput.write(outputString)
            outputString = newOutputFile
        return outputString

    @classmethod
    def checkForRfluxParameters(cls, fileVal):
        with open(fileVal)as rfluxFile:
            rfluxString = rfluxFile.read()
        assert '#@rfluxmtx' in rfluxString, \
            "The file %s does not have any rfluxmtx control parameters."
        return True

    senderFile = RadiancePath('sender','sender file')
    receiverFile = RadiancePath('receiver','receiver file')
    octreeFile = RadiancePath('octree','octree file')
    radFiles = RadiancePath('radFiles','system rad files')

    def __init__(self,senderFile=None,receiverFile=None,octreeFile=None,
                 radFiles=None):

        RadianceCommand.__init__(self)

        self.senderFile = senderFile
        """Sender file will be either a rad file containing rfluxmtx variables
         or just a - """

        self.receiverFile = receiverFile
        """Receiver file will usually be the sky file containing rfluxmtx
        variables"""

        self.octreeFile = octreeFile
        """Octree file containing the other rad file in the scene."""

        self.radFiles = radFiles
        """Rad files other than the sender and receiver that are a part of the
          scene."""

    @property
    def rfluxmtxParameters(self):
        return self.__rfluxmtxParameters

    @rfluxmtxParameters.setter
    def rfluxmtxParameters(self,parameters):
        self.__rfluxmtxParameters = parameters if parameters is not None\
            else RfluxmtxParameters()

        assert hasattr(self.rfluxmtxParameters, "isRadianceParameters"), \
            "input rfluxmtxParameters is not a valid parameters type."

    def toRadString(self, relativePath=False):
        pass