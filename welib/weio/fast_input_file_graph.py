import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Local 
try:
    from .tools.graph import *
except ImportError:
    from welib.FEM.graph import *


# --------------------------------------------------------------------------------}
# --- Wrapper to convert a "fast" input file dictionary into a graph
# --------------------------------------------------------------------------------{
def fastToGraph(data):
    if 'BeamProp' in data.keys():
        return subdynToGraph(data)
    
    if 'SmplProp' in data.keys():
        return hydrodynToGraph(data)

    if 'DOF2Nodes' in data.keys():
        return subdynSumToGraph(data)

    raise NotImplementedError('Graph for object with keys: {}'.format(data.keys()))

# --------------------------------------------------------------------------------}
# --- SubDyn
# --------------------------------------------------------------------------------{
def subdynToGraph(sd):
    """
    sd: dict-like object as returned by weio
    """
    type2Color=[
            (0.1,0.1,0.1), # Watchout based on background
            (0.753,0.561,0.05),  # 1 Beam
            (0.541,0.753,0.05),  # 2 Cable
            (0.753,0.05,0.204),  # 3 Rigid
            (0.918,0.702,0.125), # 3 Rigid
        ]

    Graph = GraphModel()
    # --- Properties
    if 'BeamProp' in sd.keys():
        BProps     = sd['BeamProp']
        Graph.addNodePropertySet('Beam')
        for ip,P in enumerate(BProps):
            prop= NodeProperty(ID=P[0], E=P[1], G=P[2], rho=P[3], D=P[4], t=P[5] )
            Graph.addNodeProperty('Beam',prop)

    if 'CableProp' in sd.keys():
        CProps     = sd['CableProp']
        Graph.addNodePropertySet('Cable')
        for ip,P in enumerate(CProps):
            Chan = -1 if len(P)<5 else P[4]
            prop= NodeProperty(ID=P[0], EA=P[1], rho=P[2], T0=P[3], Chan=Chan)
            Graph.addNodeProperty('Cable',prop)

    if 'RigidProp' in sd.keys():
        RProps     = sd['RigidProp']
        Graph.addNodePropertySet('Rigid')
        for ip,P in enumerate(RProps):
            prop= NodeProperty(ID=P[0], rho=P[1])
            Graph.addNodeProperty('Rigid',prop)

    # --- Nodes and DOFs
    Nodes     = sd['Joints']
    for iNode,N in enumerate(Nodes):
        Type= 1 if len(N)<=4 else N[4]
        node = Node(ID=N[0], x=N[1], y=N[2], z=N[3], Type=Type)
        Graph.addNode(node)

    # --- Elements
    Members  = sd['Members'].astype(int)
    PropSets = ['Beam','Cable','Rigid']
    for ie,E in enumerate(Members):
        Type=1 if len(E)==5 else E[5]
        #elem= Element(E[0], E[1:3], propset=PropSets[Type-1], propIDs=E[3:5], Type=PropSets[Type-1])
        elem= Element(E[0], E[1:3], Type=PropSets[Type-1])
        elem.data['object']='cylinder'
        elem.data['color'] = type2Color[Type]
        Graph.addElement(elem)
        # Nodal prop data
        Graph.setElementNodalProp(elem, propset=PropSets[Type-1], propIDs=E[3:5])

    # Nodal data
    for iN,N in enumerate(sd['InterfaceJoints']):
        nodeID   = int(N[0])
        Graph.setNodalData(nodeID,IBC=N[1:])
    for iN,N in enumerate(sd['BaseJoints']):
        NN=[int(n) if i<7 else n for i,n in enumerate(N)]
        nodeID   = NN[0]
        Graph.setNodalData(nodeID,RBC=NN[1:])
    #     print('CMass')
    #     print(sd['ConcentratedMasses'])

    return Graph





# --------------------------------------------------------------------------------}
# --- HydroDyn
# --------------------------------------------------------------------------------{
def hydrodynToGraph(hd):
    """
     hd: dict-like object as returned by weio
    """
    def type2Color(Pot):
        if Pot:
            return (0.753,0.05,0.204),  # Pot flow
        else:
            return (0.753,0.561,0.05),  # Morison


    Graph = GraphModel()

    # --- Properties
    if 'AxCoefs' in hd.keys():
        Props     = hd['AxCoefs']
        Graph.addNodePropertySet('AxCoefs')
        for ip,P in enumerate(Props):
            prop= NodeProperty(ID=P[0], JointAxCd=P[1], JointAxCa=P[2], JointAxCp=P[3])
            Graph.addNodeProperty('AxCoefs',prop)
    if 'SectionProp' in hd.keys():
        Props     = hd['SectionProp']
        Graph.addNodePropertySet('Section')
        for ip,P in enumerate(Props):
            # PropSetID    PropD         PropThck
            prop= NodeProperty(ID=P[0], D=P[1], t=P[2])
            Graph.addNodeProperty('Section',prop)
    if 'SmplProp' in hd.keys():
        Props     = hd['SmplProp']
        Graph.addNodePropertySet('Smpl')
        for ip,P in enumerate(Props):
            #      SimplCd    SimplCdMG    SimplCa    SimplCaMG    SimplCp    SimplCpMG   SimplAxCd  SimplAxCdMG   SimplAxCa  SimplAxCaMG  SimplAxCp   SimplAxCpMG
            if len(P)==12:
                prop= NodeProperty(ID=ip+1, Cd=P[0], CdMG=P[1], Ca=P[2], CaMG=P[3], Cp=P[4], CpMG=P[5], AxCd=P[6], AxCdMG=P[7], AxCa=P[8], AxCaMG=P[9], AxCp=P[10], AxCpMG=P[11])
            elif len(P)==10:
                prop= NodeProperty(ID=ip+1, Cd=P[0], CdMG=P[1], Ca=P[2], CaMG=P[3], Cp=P[4], CpMG=P[5], AxCa=P[6], AxCaMG=P[7], AxCp=P[8], AxCpMG=P[9])
            else:
                raise NotImplementedError()
            Graph.addNodeProperty('Smpl',prop)
    if 'DpthProp' in hd.keys():
        Props     = hd['DpthProp']
        Graph.addMiscPropertySet('Dpth')
        for ip,P in enumerate(Props):
            # Dpth      DpthCd   DpthCdMG   DpthCa   DpthCaMG       DpthCp   DpthCpMG   DpthAxCd   DpthAxCdMG   DpthAxCa   DpthAxCaMG   DpthAxCp   DpthAxCpMG
            prop= Property(ID=ip+1, Dpth=P[0], Cd=P[1], CdMG=P[2], Ca=P[3], CaMG=P[4], Cp=P[5], CpMG=P[6], AxCd=P[7], AxCdMG=P[8], AxCa=P[9], AxCaMG=P[10], AxCp=P[11], AxCpMG=P[12])
            Graph.addMiscProperty('Dpth',prop)
    if 'MemberProp' in hd.keys():
        # MemberID    MemberCd1     MemberCd2    MemberCdMG1   MemberCdMG2    MemberCa1     MemberCa2    MemberCaMG1   MemberCaMG2    MemberCp1     MemberCp2    MemberCpMG1   MemberCpMG2   MemberAxCd1   MemberAxCd2  MemberAxCdMG1 MemberAxCdMG2  MemberAxCa1   MemberAxCa2  MemberAxCaMG1 MemberAxCaMG2  MemberAxCp1  MemberAxCp2   MemberAxCpMG1   MemberAxCpMG2
        pass # TODO
    # ---------------------- FILLED MEMBERS ------------------------------------------
    #              0   NFillGroups     - Number of filled member groups (-) [If FillDens = DEFAULT, then FillDens = WtrDens; FillFSLoc is related to MSL2SWL]
    # FillNumM FillMList             FillFSLoc     FillDens
    # (-)      (-)                   (m)           (kg/m^3)
    # ---------------------- MARINE GROWTH -------------------------------------------
    #              0   NMGDepths      - Number of marine-growth depths specified (-)
    # MGDpth     MGThck       MGDens
    # (m)        (m)         (kg/m^3)

    # --- Nodes
    Nodes     = hd['Joints']
    for iNode,N in enumerate(Nodes):
        node = Node(ID=N[0], x=N[1], y=N[2], z=N[3])
        Graph.addNode(node)
        Graph.setNodeNodalProp(node, 'AxCoefs', N[4])
   
    # --- Elements
    PropSets=['Smpl','Dpth','Member']
    Members   = hd['Members']
    for ie,E in enumerate(Members):
        # MemberID  MJointID1  MJointID2  MPropSetID1  MPropSetID2  MDivSize   MCoefMod  PropPot 
        EE   = E[:5].astype(int)
        Type = int(E[6]) # MCoefMod
        Pot  = E[7].lower()[0]=='t'
        elem= Element(EE[0], EE[1:3], CoefMod=PropSets[Type-1], DivSize=E[5], Pot=Pot)
        elem.data['object']='cylinder'
        elem.data['color'] = type2Color(Pot)
        Graph.addElement(elem)
        # Nodal prop data
        Graph.setElementNodalProp(elem, propset='Section', propIDs=EE[3:5])
        if Type==1:
            # Simple
            Graph.setElementNodalProp(elem, propset='Smpl', propIDs=[1,1])
        else:
            print('>>> TODO type Depth and member')

    return Graph


# --------------------------------------------------------------------------------}
# --- SubDyn Summary file 
# --------------------------------------------------------------------------------{
def subdynSumToGraph(data):
    """ 
     data: dict-like object as returned by weio
    """
    type2Color=[
            (0.1,0.1,0.1), # Watchout based on background
            (0.753,0.561,0.05),  # 1 Beam
            (0.541,0.753,0.05),  # 2 Cable
            (0.753,0.05,0.204),  # 3 Rigid
            (0.918,0.702,0.125), # 3 Rigid
        ]

    #print(data.keys())
    DOF2Nodes = data['DOF2Nodes']
    nDOF      = data['nDOF_red']

    Graph = GraphModel()

    # --- Nodes and DOFs
    Nodes = data['Nodes']
    for iNode,N in enumerate(Nodes):
        if len(N)==9: # Temporary fix
            #N[4]=np.float(N[4].split()[0])
            N=N.astype(np.float32)
        ID = int(N[0])
        nodeDOFs=DOF2Nodes[(DOF2Nodes[:,1]==ID),0] # NOTE: these were reindex to start at 0
        node = Node(ID=ID, x=N[1], y=N[2], z=N[3], Type=int(N[4]), DOFs=nodeDOFs)
        Graph.addNode(node)

    # --- Elements
    Elements = data['Elements']
    for ie,E in enumerate(Elements):
        nodeIDs=[int(E[1]),int(E[2])]
        #  shear_[-]       Ixx_[m^4]       Iyy_[m^4]       Jzz_[m^4]          T0_[N]
        D = np.sqrt(E[7]/np.pi)*4 # <<< Approximation basedon area TODO use I as well
        elem= Element(int(E[0]), nodeIDs, Type=int(E[5]), Area=E[7], rho=E[8], E=E[7], G=E[8], D=D)
        elem.data['object']='cylinder'
        elem.data['color'] = type2Color[int(E[5])]
        Graph.addElement(elem)

    #print(self.extent)
    #print(self.maxDimension)

    # --- Graph Modes
    # Very important sortDims should be None to respect order of nodes
    dispGy, posGy, InodesGy, dispCB, posCB, InodesCB = data.getModes(sortDim=None) 
    for iMode in range(dispGy.shape[2]):
        Graph.addMode(displ=dispGy[:,:,iMode],name='GY{:d}'.format(iMode+1), freq=1/(2*np.pi))

    for iMode in range(dispCB.shape[2]):
        Graph.addMode(displ=dispCB[:,:,iMode],name='CB{:d}'.format(iMode+1), freq=data['CB_frequencies'][iMode]) 

    #print(Graph.toJSON())


    return Graph



if __name__ == '__main__':
    import weio

    filename='../../data/Monopile/MT100_SD.dat'
    # filename='../../_data/Monopile/TetraSpar_SubDyn_v3.dat'

    sd = weio.FASTInputFile(filename)
#     sd.write('OutMT.dat')
    Graph = sd.toGraph()
    Graph.divideElements(2)
    print(Graph)
    print(Graph.sortNodesBy('z'))
    # print(Graph.nodalDataFrame(sortBy='z'))
    print(Graph.points)
    print(Graph.connectivity)
    print(Graph)

# import numpy as np
# import matplotlib.pyplot as plt
# from matplotlib import collections  as mc
# from mpl_toolkits.mplot3d import Axes3D
# fig = plt.figure()
# ax = fig.add_subplot(1,2,1,projection='3d')
# 
# lines=Graph.toLines(output='coord')
# for l in lines:
# #     ax.add_line(l)
#     ax.plot(l[:,0],l[:,1],l[:,2])
# 
# ax.autoscale()
# ax.set_xlim([-40,40])
# ax.set_ylim([-40,40])
# ax.set_zlim([-40,40])
# # ax.margins(0.1)
# 
# plt.show()


