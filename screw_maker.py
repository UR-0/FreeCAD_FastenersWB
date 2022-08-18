#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  screw_maker2_0.py
#


"""
Macro to generate screws with FreeCAD.
Version 1.4 from 1st of September 2013
Version 1.5 from 23rd of December 2013
Corrected hex-heads above M12 not done.
Version 1.6 from 15th of March 2014
Added PySide support

Version 1.7 from April 2014
fixed bool type error. (int is not anymore accepted at linux)
fixed starting point of real thread at some screw types.

Version 1.8 from July 2014
first approach for a faster real thread

Version 1.9 / 2.0 July 2015
new calculation of starting point of thread
shell-based approach for screw generation
added:
ISO 14582 Hexalobular socket countersunk head screws, high head
ISO 14584 Hexalobular socket raised countersunk head screws
ISO 7380-2 Hexagon socket button head screws with collar
DIN 967 Cross recessed pan head screws with collar
ISO 4032 Hexagon nuts, Style 1
ISO 4033 Hexagon nuts, Style 2
ISO 4035 Hexagon thin nuts, chamfered
EN 1661 Hexagon nuts with flange
ISO 7094 definitions  Plain washers - Extra large series
ISO 7092 definitions  Plain washers - Small series
ISO 7093-1 Plain washer - Large series
Screw-tap to drill inner threads in parts with user defined length

ScrewMaker can now also used as a python module.
The following shows how to generate a screw from a python script:
  import screw_maker2_0

  threadDef = 'M3.5'
  o = screw_maker2_0.Screw()
  t = screw_maker2_0.Screw.setThreadType(o,'real')
  # Creates a Document-Object with label describing the screw
  d = screw_maker2_0.Screw.createScrew(o, 'ISO1207', threadDef, '20', 'real')

  # creates a shape in memory
  t = screw_maker2_0.Screw.setThreadType(o,'real')
  s = screw_maker1_9d.Screw.makeCountersunkHeadScrew(o, 'ISO14582', threadDef, 40.0)
  Part.show(s)



to do: check ISO7380 usage of rs and rt, actual only rs is used
check chamfer angle on hexogon heads and nuts
***************************************************************************
*   Copyright (c) 2013, 2014, 2015                                        *
*   Ulrich Brammer <ulrich1a[at]users.sourceforge.net>                    *
*                                                                         *
*   This file is a supplement to the FreeCAD CAx development system.      *
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU Lesser General Public License (LGPL)    *
*   as published by the Free Software Foundation; either version 2 of     *
*   the License, or (at your option) any later version.                   *
*   for detail see the LICENCE text file.                                 *
*                                                                         *
*   This software is distributed in the hope that it will be useful,      *
*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
*   GNU Library General Public License for more details.                  *
*                                                                         *
*   You should have received a copy of the GNU Library General Public     *
*   License along with this macro; if not, write to the Free Software     *
*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
*   USA                                                                   *
*                                                                         *
***************************************************************************
"""

__author__ = "Ulrich Brammer <ulrich1a@users.sourceforge.net>"



import errno
import FreeCAD, FreeCADGui, Part, math, os
from FreeCAD import Base
import DraftVecUtils
from pathlib import Path
import importlib

from utils import csv2dict
#from FastenersCmd import FastenerAttribs

#import FSmakeCountersunkHeadScrew
#from FSmakeCountersunkHeadScrew import *

DEBUG = False # set to True to show debug messages; does not work, still todo.

# import fastener data
__dir__ = os.path.dirname(__file__)
fsdatapath = os.path.join(__dir__, 'FsData')

# function to open a csv file and convert it to a dictionary


FsData = {}
FsTitles = {}
filelist = Path(fsdatapath).glob('*.csv')
for item in filelist:
    tables = csv2dict(str(item), item.stem, fieldsnamed=True)
    for tablename in tables.keys():
        if tablename == 'titles':
            FsTitles.update(tables[tablename])
        else:
            if item.stem == "tuningTable":
                FreeCAD.Console.PrintMessage(tablename + "<<\n")
            FsData[tablename] = tables[tablename]

class Screw:
    def __init__(self):
        self.objAvailable = True
        self.Tuner = 510
        self.leftHanded = False
        # thread scaling for 3D printers
        # scaled_diam = diam * ScaleA + ScaleB
        self.sm3DPrintMode = False
        self.smNutThrScaleA = 1.0
        self.smNutThrScaleB = 0.0
        self.smScrewThrScaleA = 1.0
        self.smScrewThrScaleB = 0.0

    def createScrew(self, function, fastenerAttribs):
        # self.simpThread = self.SimpleScrew.isChecked()
        # self.symThread = self.SymbolThread.isChecked()
        # FreeCAD.Console.PrintMessage(NL_text + "\n")
        if not self.objAvailable:
            return None
        try:
            if fastenerAttribs.calc_len is not None:
                fastenerAttribs.calc_len = self.getLength(fastenerAttribs.calc_len)
            if not hasattr(self, function):
                module = "FsFunctions.FS" + function
                setattr(Screw, function, getattr(importlib.import_module(module), function))
        except ValueError:
            # print "Error! nom_dia and length values must be valid numbers!"
            FreeCAD.Console.PrintMessage("Error! nom_dia and length values must be valid numbers!\n")
            return None


        if (fastenerAttribs.diameter == "Custom"):
             fastenerAttribs.dimTable = None
        else:
             fastenerAttribs.dimTable = FsData[fastenerAttribs.type + "def"][fastenerAttribs.diameter]
        self.leftHanded = fastenerAttribs.leftHanded
        # self.fastenerLen = l
        # fa.type = ST_text
        # fa.calc_diam = ND_text
        # self.customPitch = customPitch
        # self.customDia = customDia
        doc = FreeCAD.activeDocument()

        if function != "" :
            function = "self." + function + "(fastenerAttribs)"
            screw = eval(function)
            done = True
        else:
            FreeCAD.Console.PrintMessage("No suitable function for " + fastenerAttribs.type + " Screw Type!\n")
            return None
        #Part.show(screw)    
        return screw
        
    def moveScrew(self, ScrewObj_m):
        # FreeCAD.Console.PrintMessage("In Move Screw: " + str(ScrewObj_m) + "\n")

        mylist = FreeCAD.Gui.Selection.getSelectionEx()
        if mylist.__len__() == 1:
            # check selection
            # FreeCAD.Console.PrintMessage("Selections: " + str(mylist.__len__()) + "\n")
            Pnt1 = None
            Axis1 = None
            Axis2 = None

            for o in Gui.Selection.getSelectionEx():
                # for s in o.SubElementNames:
                # FreeCAD.Console.PrintMessage( "name: " + str(s) + "\n")
                for s in o.SubObjects:
                    # FreeCAD.Console.PrintMessage( "object: "+ str(s) + "\n")
                    if hasattr(s, "Curve"):
                        # FreeCAD.Console.PrintMessage( "The Object is a Curve!\n")
                        if hasattr(s.Curve, "Center"):
                            """
                   FreeCAD.Console.PrintMessage( "The object has a Center!\n")
                   FreeCAD.Console.PrintMessage( "Curve attribute. "+ str(s.__getattribute__('Curve')) + "\n")
                   FreeCAD.Console.PrintMessage( "Center: "+ str(s.Curve.Center) + "\n")
                   FreeCAD.Console.PrintMessage( "Axis: "+ str(s.Curve.Axis) + "\n")
                   """
                            Pnt1 = s.Curve.Center
                            Axis1 = s.Curve.Axis
                    if hasattr(s, 'Surface'):
                        # print 'the object is a face!'
                        if hasattr(s.Surface, 'Axis'):
                            Axis1 = s.Surface.Axis

                    if hasattr(s, 'Point'):
                        # FreeCAD.Console.PrintMessage( "the object seems to be a vertex! "+ str(s.Point) + "\n")
                        Pnt1 = s.Point

            if Axis1 is not None:
                # FreeCAD.Console.PrintMessage( "Got Axis1: " + str(Axis1) + "\n")
                Axis2 = Base.Vector(0.0, 0.0, 1.0)
                Axis2_minus = Base.Vector(0.0, 0.0, -1.0)

                # Calculate angle
                if Axis1 == Axis2:
                    normvec = Base.Vector(1.0, 0.0, 0.0)
                    result = 0.0
                else:
                    if Axis1 == Axis2_minus:
                        normvec = Base.Vector(1.0, 0.0, 0.0)
                        result = math.pi
                    else:
                        normvec = Axis1.cross(Axis2)  # Calculate axis of rotation = normvec
                        normvec.normalize()  # Normalize for quaternion calculations
                        # normvec_rot = normvec
                        result = DraftVecUtils.angle(Axis1, Axis2, normvec)  # Winkelberechnung
                sin_res = math.sin(result / 2.0)
                cos_res = math.cos(result / 2.0)
                normvec.multiply(-sin_res)  # Calculation of the quaternion elements
                # FreeCAD.Console.PrintMessage( "Angle = "+ str(math.degrees(result)) + "\n")
                # FreeCAD.Console.PrintMessage("Normal vector: "+ str(normvec) + "\n")

                pl = FreeCAD.Placement()
                pl.Rotation = (normvec.x, normvec.y, normvec.z, cos_res)  # Drehungs-Quaternion

                # FreeCAD.Console.PrintMessage("pl mit Rot: "+ str(pl) + "\n")
                # neuPlatz = Part2.Object.Placement.multiply(pl)
                neuPlatz = ScrewObj_m.Placement
                # FreeCAD.Console.PrintMessage("the Position     "+ str(neuPlatz) + "\n")
                neuPlatz.Rotation = pl.Rotation.multiply(ScrewObj_m.Placement.Rotation)
                neuPlatz.move(Pnt1)
                # FreeCAD.Console.PrintMessage("the rot. Position: "+ str(neuPlatz) + "\n")

    # DIN 7998 Wood Thread
    # zs: z position of start of the threaded part
    # ze: z position of end of the flat portion of screw (just where the tip starts) 
    # zt: z position of screw tip
    # ro: outer radius
    # ri: inner radius
    # p:  thread pitch
    def makeDin7998Thread(self, zs, ze, zt, ri, ro, p):
        epsilon = 0.03                          # epsilon needed since OCCT struggle to handle overlaps
        tph = ro - ri                           # thread profile height
        tphb = tph / math.tan(math.radians(60)) # thread profile half base
        tpratio = 0.5                           # size ratio between tip start thread and standard thread 
        tph2 = tph * tpratio
        tphb2 = tphb * tpratio
        tipH = ze - zt
        # tip thread profile
        Pnt0a = FreeCAD.Vector(0.0, 0.0, -tphb2)
        Pnt1a = FreeCAD.Vector(0.0, 0.0, tphb2)
        Pnt2a = FreeCAD.Vector(2.0 * tphb2, 0.0, tphb2)

        edge1a = Part.makeLine(Pnt0a, Pnt1a)
        edge2a = Part.makeLine(Pnt1a, Pnt2a)
        edge3a = Part.makeLine(Pnt2a, Pnt0a)

        aWire = Part.Wire([edge1a, edge2a, edge3a])
        aWire.translate(FreeCAD.Vector(epsilon, 0.0, 3.0 * tphb2))

        # top thread profile
        Pnt0b = FreeCAD.Vector(0.0, 0.0, -tphb)
        Pnt1b = FreeCAD.Vector(0.0, 0.0, tphb)
        Pnt2b = FreeCAD.Vector(tph, 0.0, 0.0)

        edge1b = Part.makeLine(Pnt0b, Pnt1b)
        edge2b = Part.makeLine(Pnt1b, Pnt2b)
        edge3b = Part.makeLine(Pnt2b, Pnt0b)

        bWire = Part.Wire([edge1b, edge2b, edge3b])
        #bWire.translate(FreeCAD.Vector(ri - epsilon, 0.0, ze + tphb))
        bWire.translate(FreeCAD.Vector(ri - epsilon, 0.0, tphb + tipH))
        
        # create helix for tip thread part
        numTurns = math.floor(tipH / p)
        #Part.show(hlx)
        hlx = Part.makeLongHelix(p, numTurns * p, 5, 0, self.leftHanded)
        sweep = Part.BRepOffsetAPI.MakePipeShell(hlx)
        sweep.setFrenetMode(True)
        sweep.setTransitionMode(1)  # right corner transition
        sweep.add(aWire)
        sweep.add(bWire)
        if sweep.isReady():
            sweep.build()
            sweep.makeSolid()
            tip_solid = sweep.shape()
            tip_solid.translate(FreeCAD.Vector(0.0, 0.0, zt))
            #Part.show(tip_solid)
        else:
            raise RuntimeError("Failed to create woodscrew tip thread")

        # create helix for body thread part
        hlx = Part.makeLongHelix(p, zs - ze, 5, 0, self.leftHanded)
        hlx.translate(FreeCAD.Vector(0.0, 0.0, tipH))
        sweep = Part.BRepOffsetAPI.MakePipeShell(hlx)
        sweep.setFrenetMode(True)
        sweep.setTransitionMode(1)  # right corner transition
        sweep.add(bWire)
        if sweep.isReady():
            sweep.build()
            sweep.makeSolid()
            body_solid = sweep.shape()
            body_solid.translate(FreeCAD.Vector(0.0, 0.0, zt))
            #Part.show(body_solid)
        else:
            raise RuntimeError("Failed to create woodscrew body thread")

        thread_solid = body_solid.fuse(tip_solid)
        # rotate the thread solid to prevent OCC errors due to cylinder seams aligning
        thread_solid.rotate(Base.Vector(0, 0, 0), Base.Vector(0, 0, 1), 180)
        #Part.show(thread_solid, "thread_solid")
        return thread_solid


    def makeHextool(self, s_hex, k_hex, cir_hex):
        # makes a cylinder with an inner hex hole, used as cutting tool
        # create hexagon face
        mhex = Base.Matrix()
        mhex.rotateZ(math.radians(60.0))
        polygon = []
        vhex = Base.Vector(s_hex / math.sqrt(3.0), 0.0, -k_hex * 0.1)
        for i in range(6):
            polygon.append(vhex)
            vhex = mhex.multiply(vhex)
        polygon.append(vhex)
        hexagon = Part.makePolygon(polygon)
        hexagon = Part.Face(hexagon)

        # create circle face
        circ = Part.makeCircle(cir_hex / 2.0, Base.Vector(0.0, 0.0, -k_hex * 0.1))
        circ = Part.Face(Part.Wire(circ))

        # Create the face with the circle as outline and the hexagon as hole
        face = circ.cut(hexagon)

        # Extrude in z to create the final cutting tool
        exHex = face.extrude(Base.Vector(0.0, 0.0, k_hex * 1.2))
        # Part.show(exHex)
        return exHex

    def makeShellthread(self, dia, P, blen, withcham, ztop, tlen = -1):
        """
    Construct a 60 degree screw thread with diameter dia,
    pitch P. 
    blen is the length of the shell body.
    tlen is the length of the threaded part (-1 = same as body length).
    if withcham == True, the end of the thread is nicely chamfered.
    The thread is constructed z-up, as a shell, with the top circular
    face removed. The top of the shell is centered @ (0, 0, ztop)
    """
        # make a cylindrical solid, then cut the thread profile from it
        H = math.sqrt(3) / 2 * P
        # move the very bottom of the base up a tiny amount
        # prevents some too-small edges from being created
        correction = 1e-5
        if tlen < 0:
            tlen = blen
        base_pnts = list(map(lambda x: Base.Vector(x),
                             [
                                 [dia / 2, 0, 0],
                                 [dia / 2, 0, -blen + P / 2],
                                 [dia / 2 - P / 2, 0, -blen + correction],
                                 [0, 0, -blen + correction],
                                 [0, 0, 0],
                                 [dia / 2, 0, -blen + correction]
                             ]))
        if withcham:
            base_profile = Part.Wire([
                Part.makeLine(base_pnts[0], base_pnts[1]),
                Part.makeLine(base_pnts[1], base_pnts[2]),
                Part.makeLine(base_pnts[2], base_pnts[3]),
                Part.makeLine(base_pnts[3], base_pnts[4]),
                Part.makeLine(base_pnts[4], base_pnts[0]),
            ])
        else:
            base_profile = Part.Wire([
                Part.makeLine(base_pnts[0], base_pnts[5]),
                Part.makeLine(base_pnts[5], base_pnts[3]),
                Part.makeLine(base_pnts[3], base_pnts[4]),
                Part.makeLine(base_pnts[4], base_pnts[0]),
            ])
        base_shell = base_profile.revolve(
            Base.Vector(0, 0, 0),
            Base.Vector(0, 0, 1),
            360)
        base_body = Part.makeSolid(base_shell)
        trotations = blen // P + 1

        # create a sketch profile of the thread
        # ref: https://en.wikipedia.org/wiki/ISO_metric_screw_thread
        fillet_r = P * math.sqrt(3) / 12
        helix_height = trotations * P
        pnts = list(map(lambda x: Base.Vector(x),
                        [
                            [dia / 2 + math.sqrt(3) * 3 / 80 * P, 0, -0.475 * P],
                            [dia / 2 - 0.625 * H, 0, -1 * P / 8],
                            [dia / 2 - 0.625 * H - 0.5 * fillet_r, 0, 0],
                            [dia / 2 - 0.625 * H, 0, P / 8],
                            [dia / 2 + math.sqrt(3) * 3 / 80 * P, 0, 0.475 * P]
                        ]))
        thread_profile_wire = Part.Wire([
            Part.makeLine(pnts[0], pnts[1]),
            Part.Arc(pnts[3], pnts[2], pnts[1]).toShape(),
            Part.makeLine(pnts[3], pnts[4]),
            Part.makeLine(pnts[4], pnts[0])])
        thread_profile_wire.translate(Base.Vector(0, 0, -1 * helix_height))
        # make the helical paths to sweep along
        # NOTE: makeLongHelix creates slightly conical
        # helices unless the 4th parameter is set to 0!
        main_helix = Part.makeLongHelix(P, helix_height, dia / 2, 0, self.leftHanded)
        lead_out_helix = Part.makeLongHelix(P, P / 2, dia / 2 + 0.5 * (5 / 8 * H + 0.5 * fillet_r), 0, self.leftHanded)
        main_helix.rotate(Base.Vector(0, 0, 0), Base.Vector(1, 0, 0), 180)
        lead_out_helix.translate(Base.Vector(0.5 * (-1 * (5 / 8 * H + 0.5 * fillet_r)), 0, 0))
        sweep_path = Part.Wire([main_helix, lead_out_helix])
        # use Part.BrepOffsetAPI to sweep the thread profile
        # ref: https://forum.freecadweb.org/viewtopic.php?t=21636#p168339
        sweep = Part.BRepOffsetAPI.MakePipeShell(sweep_path)
        sweep.setFrenetMode(True)
        sweep.setTransitionMode(1)  # right corner transition
        sweep.add(thread_profile_wire)
        if sweep.isReady():
            sweep.build()
        else:
            # geometry couldn't be generated in a useable form
            raise RuntimeError("Failed to create shell thread: could not sweep thread")
        sweep.makeSolid()
        swept_solid = sweep.shape()
        # translate swept path slightly for backwards compatibility
        toffset = blen - tlen + P / 2
        minoffset = 5 * P / 8
        if (toffset < minoffset):
            toffset = minoffset

        swept_solid.translate(Base.Vector(0, 0, -toffset))
        # perform the actual boolean operations
        base_body.rotate(Base.Vector(0, 0, 0), Base.Vector(0, 0, 1), 90)
        threaded_solid = base_body.cut(swept_solid)
        if toffset < 0:
            # one more component: a kind of 'cap' to improve behaviour with
            # large offset values
            cap_bottom_point = Base.Vector(0, 0, - dia / 2)
            cap_profile = Part.Wire([
                Part.makeLine(base_pnts[4], base_pnts[0]),
                Part.makeLine(base_pnts[0], cap_bottom_point),
                Part.makeLine(cap_bottom_point, base_pnts[4])])
            cap_shell = cap_profile.revolve(
                Base.Vector(0, 0, 0),
                Base.Vector(0, 0, 1),
                360)
            cap_solid = Part.makeSolid(cap_shell)
            # threaded_solid = threaded_solid.fuse(cap_solid)
            threaded_solid.removeSplitter
        # remove top face(s) and convert to a shell
        result = Part.Shell([x for x in threaded_solid.Faces \
                             if not abs(x.CenterOfMass[2]) < 1e-7])
        result.translate(Base.Vector(0, 0, ztop))
        return result

    # if da is not None: make Shell for a nut else: make a screw tap
    def makeInnerThread_2(self, d, P, rotations, da, l):
        d = float(d)
        bot_off = 0.0  # nominal length

        if d > 52.0:
            fuzzyValue = 5e-5
        else:
            fuzzyValue = 0.0

        H = P * math.cos(math.radians(30))  # Thread depth H
        r = d / 2.0

        helix = Part.makeLongHelix(P, P, d * self.Tuner / 1000.0, 0, self.leftHanded)  # make just one turn, length is identical to pitch
        helix.translate(FreeCAD.Vector(0.0, 0.0, -P * 9.0 / 16.0))

        extra_rad = P

        # points for inner thread profile
        ps0 = (r, 0.0, 0.0)
        ps1 = (r - H * 5.0 / 8.0, 0.0, -P * 5.0 / 16.0)
        ps2 = (r - H * 5.0 / 8.0, 0.0, -P * 9.0 / 16.0)
        ps3 = (r, 0.0, -P * 14.0 / 16.0)
        ps4 = (r + H * 1 / 24.0, 0.0, -P * 31.0 / 32.0)  # Center of Arc
        ps5 = (r, 0.0, -P)

        ps6 = (r + extra_rad, 0.0, -P)
        ps7 = (r + extra_rad, 0.0, 0.0)

        edge0 = Part.makeLine(ps0, ps1)
        edge1 = Part.makeLine(ps1, ps2)
        edge2 = Part.makeLine(ps2, ps3)
        edge3 = Part.Arc(FreeCAD.Vector(ps3), FreeCAD.Vector(ps4), FreeCAD.Vector(ps5)).toShape()
        edge4 = Part.makeLine(ps5, ps6)
        edge5 = Part.makeLine(ps6, ps7)
        edge6 = Part.makeLine(ps7, ps0)

        W0 = Part.Wire([edge0, edge1, edge2, edge3, edge4, edge5, edge6])
        # Part.show(W0, 'W0')

        makeSolid = True
        isFrenet = True
        pipe0 = Part.Wire(helix).makePipeShell([W0], makeSolid, isFrenet)
        # pipe1 = pipe0.copy()

        TheFaces = []
        TheFaces.append(pipe0.Faces[0])
        TheFaces.append(pipe0.Faces[1])
        TheFaces.append(pipe0.Faces[2])
        TheFaces.append(pipe0.Faces[3])
        # topHeliFaces = [pipe0.Faces[6], pipe0.Faces[8]]
        # innerHeliFaces = [pipe0.Faces[5]]
        # bottomFaces = [pipe0.Faces[4], pipe0.Faces[7]]

        TheShell = Part.Shell(TheFaces)
        # singleThreadShell = TheShell.copy()
        # print "Shellpoints: ", len(TheShell.Vertexes)
        if da is None:
            commonbox = Part.makeBox(d + 4.0 * P, d + 4.0 * P, 3.0 * P)
            commonbox.translate(FreeCAD.Vector(-(d + 4.0 * P) / 2.0, -(d + 4.0 * P) / 2.0, -(3.0) * P))
            topShell = TheShell.common(commonbox)
            top_edges = []
            top_z = -1.0e-5

            for kante in topShell.Edges:
                if kante.Vertexes[0].Point.z >= top_z and kante.Vertexes[1].Point.z >= top_z:
                    top_edges.append(kante)
                    # Part.show(kante)
            top_wire = Part.Wire(Part.__sortEdges__(top_edges))
            top_face = Part.Face(top_wire)

            TheFaces = [top_face.Faces[0]]
            TheFaces.extend(topShell.Faces)

            for i in range(rotations - 2):
                TheShell.translate(FreeCAD.Vector(0.0, 0.0, - P))
                for flaeche in TheShell.Faces:
                    TheFaces.append(flaeche)

            # FreeCAD.Console.PrintMessage("Base-Shell: " + str(i) + "\n")
            # Make separate faces for the tip of the screw
            botFaces = []
            for i in range(rotations - 2, rotations, 1):
                TheShell.translate(FreeCAD.Vector(0.0, 0.0, - P))

                for flaeche in TheShell.Faces:
                    botFaces.append(flaeche)
            # FreeCAD.Console.PrintMessage("Bottom-Shell: " + str(i) + "\n")
            # FreeCAD.Console.PrintMessage("without chamfer: " + str(i) + "\n")

            commonbox = Part.makeBox(d + 4.0 * P, d + 4.0 * P, 3.0 * P)
            commonbox.translate(FreeCAD.Vector(-(d + 4.0 * P) / 2.0, -(d + 4.0 * P) / 2.0, -(rotations) * P + bot_off))
            # commonbox.translate(FreeCAD.Vector(-(d+4.0*P)/2.0, -(d+4.0*P)/2.0,-(rotations+3)*P+bot_off))
            # Part.show(commonbox)

            BotShell = Part.Shell(botFaces)
            # Part.show(BotShell)

            BotShell = BotShell.common(commonbox)
            # BotShell = BotShell.cut(commonbox)
            bot_edges = []
            bot_z = 1.0e-5 - (rotations) * P + bot_off

            for kante in BotShell.Edges:
                if kante.Vertexes[0].Point.z <= bot_z and kante.Vertexes[1].Point.z <= bot_z:
                    bot_edges.append(kante)
                    # Part.show(kante)
            bot_wire = Part.Wire(Part.__sortEdges__(bot_edges))

            bot_face = Part.Face(bot_wire)
            bot_face.reverse()

            for flaeche in BotShell.Faces:
                TheFaces.append(flaeche)
            # if da is not None:
            # for flaeche in cham_Shell.Faces:
            # TheFaces.append(flaeche)
            # else:
            TheFaces.append(bot_face)
            TheShell = Part.Shell(TheFaces)
            TheSolid = Part.Solid(TheShell)
            # print self.Tuner, " ", TheShell.ShapeType, " ", TheShell.isValid(), " rotations: ", rotations, " Shellpoints: ", len(TheShell.Vertexes)
            return TheSolid

        else:
            # Try to make the inner thread shell of a nut
            cham_i = 2 * H * math.tan(math.radians(15.0))  # inner chamfer

            # points for chamfer: cut-Method
            pch0 = (da / 2.0 - 2 * H, 0.0, +cham_i)  # bottom chamfer
            pch1 = (da / 2.0, 0.0, 0.0)  #
            pch2 = (da / 2.0, 0.0, - 2.1 * P)
            pch3 = (da / 2.0 - 2 * H, 0.0, - 2.1 * P)  #

            # pch2 =  (da/2.0, 0.0, l)
            # pch3 =  (da/2.0 - 2*H, 0.0, l - cham_i)

            edgech0 = Part.makeLine(pch0, pch1)
            edgech1 = Part.makeLine(pch1, pch2)
            edgech2 = Part.makeLine(pch2, pch3)
            edgech3 = Part.makeLine(pch3, pch0)

            Wch_wire = Part.Wire([edgech0, edgech1, edgech2, edgech3])
            bottom_Face = Part.Face(Wch_wire)
            # bottom_Solid = bottom_Face.revolve(Base.Vector(0.0,0.0,-(rotations-1)*P),Base.Vector(0.0,0.0,1.0),360)
            bottom_Solid = bottom_Face.revolve(Base.Vector(0.0, 0.0, 0.0), Base.Vector(0.0, 0.0, 1.0), 360)
            # Part.show(cham_Solid, 'cham_Solid')
            # Part.show(Wch_wire)
            bottomChamferFace = bottom_Solid.Faces[0]

            # points for chamfer: cut-Method
            pch0t = (da / 2.0 - 2 * H, 0.0, l - cham_i)  # top chamfer
            pch1t = (da / 2.0, 0.0, l)  #
            pch2t = (da / 2.0, 0.0, l + 4 * P)
            pch3t = (da / 2.0 - 2 * H, 0.0, l + 4 * P)  #

            edgech0t = Part.makeLine(pch0t, pch1t)
            edgech1t = Part.makeLine(pch1t, pch2t)
            edgech2t = Part.makeLine(pch2t, pch3t)
            edgech3t = Part.makeLine(pch3t, pch0t)

            Wcht_wire = Part.Wire([edgech0t, edgech1t, edgech2t, edgech3t])
            top_Face = Part.Face(Wcht_wire)
            top_Solid = top_Face.revolve(Base.Vector(0.0, 0.0, (rotations - 1) * P), Base.Vector(0.0, 0.0, 1.0), 360)
            # Part.show(top_Solid, 'top_Solid')
            # Part.show(Wch_wire)
            topChamferFace = top_Solid.Faces[0]

            threeThreadFaces = TheFaces.copy()
            for k in range(1):
                TheShell.translate(FreeCAD.Vector(0.0, 0.0, P))
                for threadFace in TheShell.Faces:
                    threeThreadFaces.append(threadFace)

            chamferShell = Part.Shell(threeThreadFaces)
            # Part.show(chamferShell, 'chamferShell')
            # Part.show(bottomChamferFace, 'bottomChamferFace')

            bottomPart = chamferShell.cut(bottom_Solid)
            # Part.show(bottomPart, 'bottomPart')
            bottomFuse, bottomMap = bottomChamferFace.generalFuse([chamferShell], fuzzyValue)
            # print ('bottomMap: ', bottomMap)
            # chamFuse, chamMap = chamferShell.generalFuse([bottomChamferFace])
            # print ('chamMap: ', chamMap)
            # Part.show(bottomFuse, 'bottomFuse')
            # Part.show(bottomMap[0][0], 'bMap0')
            # Part.show(bottomMap[0][1], 'bMap1')
            innerThreadFaces = [bottomMap[0][1]]
            for face in bottomPart.Faces:
                innerThreadFaces.append(face)
            # bottomShell = Part.Shell(innerThreadFaces)
            # Part.show(bottomShell)
            bottomFaces = []
            # TheShell.translate(FreeCAD.Vector(0.0, 0.0, P))
            for k in range(1, rotations - 2):
                TheShell.translate(FreeCAD.Vector(0.0, 0.0, P))
                for threadFace in TheShell.Faces:
                    innerThreadFaces.append(threadFace)
            # testShell = Part.Shell(innerThreadFaces)
            # Part.show(testShell, 'testShell')

            chamferShell.translate(FreeCAD.Vector(0.0, 0.0, (rotations - 1) * P))
            # Part.show(chamferShell, 'chamferShell')
            # Part.show(topChamferFace, 'topChamferFace')
            topPart = chamferShell.cut(top_Solid)
            # Part.show(topPart, 'topPart')
            for face in topPart.Faces:
                innerThreadFaces.append(face)

            topFuse, topMap = topChamferFace.generalFuse([chamferShell], fuzzyValue)
            # print ('topMap: ', topMap)
            # Part.show(topMap[0][0], 'tMap0')
            # Part.show(topMap[0][1], 'tMap1')
            # Part.show(topFuse, 'topFuse')
            innerThreadFaces.append(topMap[0][1])

            # topFaces = []
            # for face in topPart.Faces:
            #  topFaces.append(face)
            # topFaces.append(topMap[0][1])
            # testTopShell = Part.Shell(topFaces)
            # Part.show(testTopShell, 'testTopShell')

            threadShell = Part.Shell(innerThreadFaces)
            # Part.show(threadShell, 'threadShell')

            return threadShell




    def cutChamfer(self, dia_cC, P_cC, l_cC):
        cham_t = P_cC * math.sqrt(3.0) / 2.0 * 17.0 / 24.0
        PntC0 = Base.Vector(0.0, 0.0, -l_cC)
        PntC1 = Base.Vector(dia_cC / 2.0 - cham_t, 0.0, -l_cC)
        PntC2 = Base.Vector(dia_cC / 2.0 + cham_t, 0.0, -l_cC + cham_t + cham_t)
        PntC3 = Base.Vector(dia_cC / 2.0 + cham_t, 0.0, -l_cC - P_cC - cham_t)
        PntC4 = Base.Vector(0.0, 0.0, -l_cC - P_cC - cham_t)

        edgeC1 = Part.makeLine(PntC0, PntC1)
        edgeC2 = Part.makeLine(PntC1, PntC2)
        edgeC3 = Part.makeLine(PntC2, PntC3)
        edgeC4 = Part.makeLine(PntC3, PntC4)
        edgeC5 = Part.makeLine(PntC4, PntC0)
        CWire = Part.Wire([edgeC1, edgeC2, edgeC3, edgeC4, edgeC5])
        # Part.show(CWire)
        CFace = Part.Face(CWire)
        cyl = CFace.revolve(Base.Vector(0.0, 0.0, 0.0), Base.Vector(0.0, 0.0, 1.0), 360)
        return cyl

    # cross recess type H
    def makeCross_H3(self, CrossType='2', m=6.9, h=0.0):
        # m = diameter of cross at top of screw at reference level for penetration depth
        b, e_mean, g, f_mean, r, t1, alpha, beta = FsData["iso4757def"][CrossType]

        rad265 = math.radians(26.5)
        rad28 = math.radians(28.0)
        tg = (m - g) / 2.0 / math.tan(rad265)  # depth at radius of g
        t_tot = tg + g / 2.0 * math.tan(rad28)  # total depth

        # print 'tg: ', tg,' t_tot: ', t_tot
        hm = m / 4.0
        hmc = m / 2.0
        rmax = m / 2.0 + hm * math.tan(rad265)

        Pnt0 = Base.Vector(0.0, 0.0, hm)
        Pnt1 = Base.Vector(rmax, 0.0, hm)
        Pnt3 = Base.Vector(0.0, 0.0, 0.0)
        Pnt4 = Base.Vector(g / 2.0, 0.0, -tg)
        Pnt5 = Base.Vector(0.0, 0.0, -t_tot)

        edge1 = Part.makeLine(Pnt0, Pnt1)
        edge3 = Part.makeLine(Pnt1, Pnt4)
        edge4 = Part.makeLine(Pnt4, Pnt5)
        # FreeCAD.Console.PrintMessage("Edges made Pnt2: " + str(Pnt2) + "\n")

        aWire = Part.Wire([edge1, edge3, edge4])
        crossShell = aWire.revolve(Pnt3, Base.Vector(0.0, 0.0, 1.0), 360)
        # FreeCAD.Console.PrintMessage("Peak-wire revolved: " + str(e_mean) + "\n")
        cross = Part.Solid(crossShell)
        # Part.show(cross)

        # the need to cut 4 corners out of the above shape.
        # Definition of corner
        # The angles 92 degrees and alpha are defined on a plane which has
        # an angle of beta against our coordinate system.
        # The projected angles are needed for easier calculation!
        rad_alpha = math.radians(alpha / 2.0)
        rad92 = math.radians(92.0 / 2.0)
        rad_beta = math.radians(beta)

        rad_alpha_p = math.atan(math.tan(rad_alpha) / math.cos(rad_beta))
        rad92_p = math.atan(math.tan(rad92) / math.cos(rad_beta))

        tb = tg + (g - b) / 2.0 * math.tan(rad28)  # depth at dimension b
        rbtop = b / 2.0 + (hmc + tb) * math.tan(rad_beta)  # radius of b-corner at hm
        rbtot = b / 2.0 - (t_tot - tb) * math.tan(rad_beta)  # radius of b-corner at t_tot

        dre = e_mean / 2.0 / math.tan(rad_alpha_p)  # delta between corner b and corner e in x direction
        # FreeCAD.Console.PrintMessage("delta calculated: " + str(dre) + "\n")

        dx = m / 2.0 * math.cos(rad92_p)
        dy = m / 2.0 * math.sin(rad92_p)

        PntC0 = Base.Vector(rbtop, 0.0, hmc)
        PntC1 = Base.Vector(rbtot, 0.0, -t_tot)
        PntC2 = Base.Vector(rbtop + dre, +e_mean / 2.0, hmc)
        PntC3 = Base.Vector(rbtot + dre, +e_mean / 2.0, -t_tot)
        PntC4 = Base.Vector(rbtop + dre, -e_mean / 2.0, hmc)
        PntC5 = Base.Vector(rbtot + dre, -e_mean / 2.0, -t_tot)

        PntC6 = Base.Vector(rbtop + dre + dx, +e_mean / 2.0 + dy, hmc)
        # PntC7 = Base.Vector(rbtot+dre+dx,+e_mean/2.0+dy,-t_tot)
        PntC7 = Base.Vector(rbtot + dre + 2.0 * dx, +e_mean + 2.0 * dy, -t_tot)
        PntC8 = Base.Vector(rbtop + dre + dx, -e_mean / 2.0 - dy, hmc)
        # PntC9 = Base.Vector(rbtot+dre+dx,-e_mean/2.0-dy,-t_tot)
        PntC9 = Base.Vector(rbtot + dre + 2.0 * dx, -e_mean - 2.0 * dy, -t_tot)

        # wire_hm = Part.makePolygon([PntC0,PntC2,PntC6,PntC8,PntC4,PntC0])
        # face_hm =Part.Face(wire_hm)
        # Part.show(face_hm)

        wire_t_tot = Part.makePolygon([PntC1, PntC3, PntC7, PntC9, PntC5, PntC1])
        # Part.show(wire_t_tot)
        edgeC1 = Part.makeLine(PntC0, PntC1)
        # FreeCAD.Console.PrintMessage("edgeC1 with PntC9" + str(PntC9) + "\n")

        makeSolid = True
        isFrenet = False
        corner = Part.Wire(edgeC1).makePipeShell([wire_t_tot], makeSolid, isFrenet)
        # Part.show(corner)

        rot_axis = Base.Vector(0., 0., 1.0)
        sin_res = math.sin(math.radians(90) / 2.0)
        cos_res = math.cos(math.radians(90) / 2.0)
        rot_axis.multiply(-sin_res)  # Calculation of Quaternion-Elements
        # FreeCAD.Console.PrintMessage("Quaternion-Elements" + str(cos_res) + "\n")

        pl_rot = FreeCAD.Placement()
        pl_rot.Rotation = (rot_axis.x, rot_axis.y, rot_axis.z, cos_res)  # Rotation-Quaternion 90° z-Axis

        crossShell = crossShell.cut(corner)
        # Part.show(crossShell)
        cutplace = corner.Placement

        cornerFaces = []
        cornerFaces.append(corner.Faces[0])
        cornerFaces.append(corner.Faces[1])
        cornerFaces.append(corner.Faces[3])
        cornerFaces.append(corner.Faces[4])

        cornerShell = Part.Shell(cornerFaces)
        cornerShell = cornerShell.common(cross)
        addPlace = cornerShell.Placement

        crossFaces = cornerShell.Faces

        for i in range(3):
            cutplace.Rotation = pl_rot.Rotation.multiply(corner.Placement.Rotation)
            corner.Placement = cutplace
            crossShell = crossShell.cut(corner)
            addPlace.Rotation = pl_rot.Rotation.multiply(cornerShell.Placement.Rotation)
            cornerShell.Placement = addPlace
            for coFace in cornerShell.Faces:
                crossFaces.append(coFace)

        # Part.show(crossShell)
        for i in range(1, 6):
            crossFaces.append(crossShell.Faces[i])

        crossShell0 = Part.Shell(crossFaces)

        crossFaces.append(crossShell.Faces[0])
        crossShell = Part.Shell(crossFaces)

        cross = Part.Solid(crossShell)

        # FreeCAD.Console.PrintMessage("Placement: " + str(pl_rot) + "\n")

        cross.Placement.Base = Base.Vector(0.0, 0.0, h)
        crossShell0.Placement.Base = Base.Vector(0.0, 0.0, h)
        # Part.show(crossShell0)
        # Part.show(cross)
        return cross, crossShell0

    # Allen recess cutting tool
    # Parameters used: s_mean, k, t_min, dk
    def makeAllen2(self, s_a=3.0, t_a=1.5, h_a=2.0, t_2=0.0):
        # h_a  top height location of cutting tool
        # s_a hex width
        # t_a dept of the allen
        # t_2 depth of center-bore

        if t_2 == 0.0:
            depth = s_a / 3.0
            e_cham = 2.0 * s_a / math.sqrt(3.0)
            # FreeCAD.Console.PrintMessage("allen tool: " + str(s_a) + "\n")

            # Points for an arc at the peak of the cone
            rCone = e_cham / 4.0
            hyp = (depth * math.sqrt(e_cham ** 2 / depth ** 2 + 1.0) * rCone) / e_cham
            radAlpha = math.atan(e_cham / depth)
            radBeta = math.pi / 2.0 - radAlpha
            zrConeCenter = hyp - depth - t_a
            xArc1 = math.sin(radBeta) * rCone
            zArc1 = zrConeCenter - math.cos(radBeta) * rCone
            xArc2 = math.sin(radBeta / 2.0) * rCone
            zArc2 = zrConeCenter - math.cos(radBeta / 2.0) * rCone
            zArc3 = zrConeCenter - rCone

            # The round part of the cutting tool, we need for the allen hex recess
            PntH1 = Base.Vector(0.0, 0.0, -t_a - depth - depth)
            PntH2 = Base.Vector(e_cham, 0.0, -t_a - depth - depth)
            PntH3 = Base.Vector(e_cham, 0.0, -t_a + depth)
            PntH4 = Base.Vector(0.0, 0.0, -t_a - depth)

            PntA1 = Base.Vector(xArc1, 0.0, zArc1)
            PntA2 = Base.Vector(xArc2, 0.0, zArc2)
            PntA3 = Base.Vector(0.0, 0.0, zArc3)

            edgeA1 = Part.Arc(PntA1, PntA2, PntA3).toShape()

            edgeH1 = Part.makeLine(PntH1, PntH2)
            edgeH2 = Part.makeLine(PntH2, PntH3)
            edgeH3 = Part.makeLine(PntH3, PntA1)
            edgeH4 = Part.makeLine(PntA3, PntH1)

            hWire = Part.Wire([edgeH1, edgeH2, edgeH3, edgeA1, edgeH4])
            hex_depth = -1.0 - t_a - depth * 1.1
        else:
            e_cham = 2.0 * s_a / math.sqrt(3.0)
            d_cent = s_a / 3.0
            depth_cent = d_cent * math.tan(math.pi / 6.0)
            depth_cham = (e_cham - d_cent) * math.tan(math.pi / 6.0)

            Pnts = [
                Base.Vector(0.0, 0.0, -t_2 - depth_cent),
                Base.Vector(0.0, 0.0, -t_2 - depth_cent - depth_cent),
                Base.Vector(e_cham, 0.0, -t_2 - depth_cent - depth_cent),
                Base.Vector(e_cham, 0.0, -t_a + depth_cham),
                Base.Vector(d_cent, 0.0, -t_a),
                Base.Vector(d_cent, 0.0, -t_2)
            ]

            edges = []
            for i in range(0, len(Pnts) - 1):
                edges.append(Part.makeLine(Pnts[i], Pnts[i + 1]))
            edges.append(Part.makeLine(Pnts[5], Pnts[0]))

            hWire = Part.Wire(edges)
            hex_depth = -1.0 - t_2 - depth_cent * 1.1

        # Part.show(hWire)
        hFace = Part.Face(hWire)
        roundtool = hFace.revolve(Base.Vector(0.0, 0.0, 0.0), Base.Vector(0.0, 0.0, 1.0), 360)

        # create hexagon
        mhex = Base.Matrix()
        mhex.rotateZ(math.radians(60.0))
        polygon = []
        vhex = Base.Vector(s_a / math.sqrt(3.0), 0.0, 1.0)
        for i in range(6):
            polygon.append(vhex)
            vhex = mhex.multiply(vhex)
        polygon.append(vhex)
        hexagon = Part.makePolygon(polygon)
        hexFace = Part.Face(hexagon)
        solidHex = hexFace.extrude(Base.Vector(0.0, 0.0, hex_depth))
        allen = solidHex.cut(roundtool)
        # Part.show(allen)

        allenFaces = [allen.Faces[0]]
        for i in range(2, len(allen.Faces)):
            allenFaces.append(allen.Faces[i])
        allenShell = Part.Shell(allenFaces)
        solidHex.Placement.Base = Base.Vector(0.0, 0.0, h_a)
        allenShell.Placement.Base = Base.Vector(0.0, 0.0, h_a)

        return solidHex, allenShell

    # ISO 10664 Hexalobular internal driving feature for bolts and screws
    def makeIso10664_3(self, RType='T20', t_hl=3.0, h_hl=0):
        # t_hl depth of the recess
        # h_hl top height location of Cutting tool
        A, B, Re = FsData["iso10664def"][RType]
        sqrt_3 = math.sqrt(3.0)
        depth = A / 4.0
        offSet = 1.0

        # Chamfer cutter for the hexalobular recess
        PntH1 = Base.Vector(0.0, 0.0, -t_hl - depth - 1.0)
        # PntH2 = Base.Vector(A/2.0*1.02,0.0,-t_hl-depth-1.0)
        # PntH3 = Base.Vector(A/2.0*1.02,0.0,-t_hl)
        PntH2 = Base.Vector(A, 0.0, -t_hl - depth - 1.0)
        PntH3 = Base.Vector(A, 0.0, -t_hl + depth)
        PntH4 = Base.Vector(0.0, 0.0, -t_hl - depth)

        # Points for an arc at the peak of the cone
        rCone = A / 4.0
        hyp = (depth * math.sqrt(A ** 2 / depth ** 2 + 1.0) * rCone) / A
        radAlpha = math.atan(A / depth)
        radBeta = math.pi / 2.0 - radAlpha
        zrConeCenter = hyp - depth - t_hl
        xArc1 = math.sin(radBeta) * rCone
        zArc1 = zrConeCenter - math.cos(radBeta) * rCone
        xArc2 = math.sin(radBeta / 2.0) * rCone
        zArc2 = zrConeCenter - math.cos(radBeta / 2.0) * rCone
        zArc3 = zrConeCenter - rCone

        PntA1 = Base.Vector(xArc1, 0.0, zArc1)
        PntA2 = Base.Vector(xArc2, 0.0, zArc2)
        PntA3 = Base.Vector(0.0, 0.0, zArc3)

        edgeA1 = Part.Arc(PntA1, PntA2, PntA3).toShape()

        edgeH1 = Part.makeLine(PntH1, PntH2)
        edgeH2 = Part.makeLine(PntH2, PntH3)
        edgeH3 = Part.makeLine(PntH3, PntA1)
        edgeH4 = Part.makeLine(PntA3, PntH1)

        hWire = Part.Wire([edgeH1, edgeH2, edgeH3, edgeA1])
        cutShell = hWire.revolve(Base.Vector(0.0, 0.0, 0.0), Base.Vector(0.0, 0.0, 1.0), 360)
        cutTool = Part.Solid(cutShell)

        Ri = -((B + sqrt_3 * (2. * Re - A)) * B + (A - 4. * Re) * A) / (4. * B - 2. * sqrt_3 * A + (4. * sqrt_3 - 8.) * Re)
        # print '2nd  Ri last solution: ', Ri
        beta = math.acos(A / (4 * Ri + 4 * Re) - (2 * Re) / (4 * Ri + 4 * Re)) - math.pi / 6
        # print 'beta: ', beta
        Rh = (sqrt_3 * (A / 2.0 - Re)) / 2.0
        Re_x = A / 2.0 - Re + Re * math.sin(beta)
        Re_y = Re * math.cos(beta)
        Ri_y = B / 4.0
        Ri_x = sqrt_3 * B / 4.0

        mhex = Base.Matrix()
        mhex.rotateZ(math.radians(60.0))
        hexlobWireList = []

        PntRe0 = Base.Vector(Re_x, -Re_y, offSet)
        PntRe1 = Base.Vector(A / 2.0, 0.0, offSet)
        PntRe2 = Base.Vector(Re_x, Re_y, offSet)
        edge0 = Part.Arc(PntRe0, PntRe1, PntRe2).toShape()
        # Part.show(edge0)
        hexlobWireList.append(edge0)

        PntRi = Base.Vector(Ri_x, Ri_y, offSet)
        PntRi2 = mhex.multiply(PntRe0)
        edge1 = Part.Arc(PntRe2, PntRi, PntRi2).toShape()
        # Part.show(edge1)
        hexlobWireList.append(edge1)

        for i in range(5):
            PntRe1 = mhex.multiply(PntRe1)
            PntRe2 = mhex.multiply(PntRe2)
            edge0 = Part.Arc(PntRi2, PntRe1, PntRe2).toShape()
            hexlobWireList.append(edge0)
            PntRi = mhex.multiply(PntRi)
            PntRi2 = mhex.multiply(PntRi2)
            if i == 5:
                edge1 = Part.Arc(PntRe2, PntRi, PntRe0).toShape()
            else:
                edge1 = Part.Arc(PntRe2, PntRi, PntRi2).toShape()
            hexlobWireList.append(edge1)
        hexlobWire = Part.Wire(hexlobWireList)
        # Part.show(hWire)

        face = Part.Face(hexlobWire)

        # Extrude in z to create the cutting tool for the screw-head-face
        Helo = face.extrude(Base.Vector(0.0, 0.0, -t_hl - depth - offSet))
        # Make the recess-shell for the screw-head-shell

        hexlob = Helo.cut(cutTool)
        # Part.show(hexlob)
        hexlobFaces = [hexlob.Faces[0]]
        for i in range(2, 15):
            hexlobFaces.append(hexlob.Faces[i])

        hexlobShell = Part.Shell(hexlobFaces)

        hexlobShell.Placement.Base = Base.Vector(0.0, 0.0, h_hl)
        Helo.Placement.Base = Base.Vector(0.0, 0.0, h_hl)

        return Helo, hexlobShell

    def setThreadType(self, TType='simple'):
        self.simpThread = False
        self.symThread = False
        self.rThread = False
        if TType == 'simple':
            self.simpThread = True
        if TType == 'symbol':
            self.symThread = True
        if TType == 'real':
            self.rThread = True

    def setTuner(self, myTuner=511):
        self.Tuner = myTuner

    def getDia(self, ThreadDiam, isNut):
        if type(ThreadDiam) == type(""):
            threadstring = ThreadDiam.strip("()")
            dia = FsData["DiaList"][threadstring][0]
        else:
            dia = ThreadDiam
        if self.sm3DPrintMode:
            if isNut:
                dia = self.smNutThrScaleA * dia + self.smNutThrScaleB
            else:
                dia = self.smScrewThrScaleA * dia + self.smScrewThrScaleB
        return dia

    def getLength(self, LenStr):
        # washers and nuts pass an int (1), for their unused length attribute
        # handle this circumstance if necessary
        if type(LenStr) == int:
            return LenStr
        # otherwise convert the string to a number using predefined rules
        if 'in' not in LenStr:
            LenFloat = float(LenStr)
        else:
            components = LenStr.strip('in').split(' ')
            total = 0
            for item in components:
                if '/' in item:
                    subcmpts = item.split('/')
                    total += float(subcmpts[0]) / float(subcmpts[1])
                else:
                    total += float(item)
            LenFloat = total * 25.4
        return LenFloat
