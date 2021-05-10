""" 
Classes and tools to easily set up a FEM model made of beam elements


References:


 [2]  Richard Schwertassek,  Oskar Wallrapp
      "Dynamik Flexibler Mehrkoerpersysteme : Methoden Der Mechanik 



"""
import numpy as np
import scipy
from welib.FEM.utils import skew 
from welib.system.eva import eig

# --------------------------------------------------------------------------------}
# --- Main wrapper functions 
# --------------------------------------------------------------------------------{
def cbeam(xNodes, m, EIx=None, EIy=None, EIz=None, EA=None, A=None, Kt=None, E=None, G=None, phi=None, 
        element='frame3d', nel=None,
        BC='clamped-free', M_root=None, M_tip=None, K_root=None, K_tip=None
        ):
    """ 
    Returns finite element model of a continuous beam
    For uniform or straight beams, the beam is assumed to be along the x direction.
    
    NOTE: input values can be vectors or scalars.
      If they are scalars, then a beam with constant properties and of length L=xNodes is used;
      If they are vectors, values per element are required
      then linear interpolation is used. The dimension of the inputs does not need to match nel

    INPUTS
    - xNodes: define beam length, beam spanwise positions or beam nodes, either:
          -  (scalar) Beam length, for uniform beam [m]
          -  (1xn) Span vector of the beam (for straight beams) [m]
          -  (2xn) Nodes positions x,z along the beam for 2d beam [m]
          -  (3xn) Nodes positions x,y,z along the beam for 3d beam [m]

    - m    : (n) Mass per length along the beam, at nodes [kg/m]

    - A    : (n) Beam cross section area along the beam, at nodes [m^2]

    - EIx  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]
    - EIy  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]
    - EIz  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]

    - Kt  : (n) Torsion constant, at nodes [m^4]

    - G   : (scalar) Shear modulus. Steel: 79.3  [Pa] [N/m^2]
    - E   : (scalar) Elastic (Young) modulus

    - phi : (1xn) rotation of principal axes wrt mean line (tangent) of the beam [rad], at nodes

    - element: specify the element type to use along the beam: 
           'frame3d'
           'frame3dlin'
           'beam2d'

    - nel  : Number of elements. If provided Structural propeties and nodes will be interpolated to match nel. 
             Otherwise, the length of xNodes determines the discretization

    - BC: string defining boundary condition:
          -'clamped-free': clamped at root, free at tip
          -'free-free': free at root, free at tip

    - M_root/tip: (6x6) additional rigid body mass matrix at beam ends

    - K_root/tip: (6x6) additional stiffness matrix at beam ends
    
    OUTPUTS
      FEM: dictionary with keys:
        - MM: (nDOF x nDOF)  Mass matrix (before BC)
        - KK: (nDOF x nDOF)  Stiffness matrix (before BC)
        - MMr: (nr x nr)     Mass matrix (after BC)
        - KKr: (nr x nr)     Stiffness matrix (after BC)
        - Tr:  (n x nr)      Boundary condition transformation matrix
        - xNodes : (3 x nel+1) Nodes locations
        - Q   : (nr x nr)    Normalized Modes
        - modeNames : (<=nr) Identified modes names
        - freq : (nr) Frequencies
    """
    # --- Assembly full FEM system
    MM, KK, xNodes, DCM, Elem2Nodes, Nodes2DOF, Elem2DOF=cbeam_assembly(xNodes,m,EIx=EIx,EIy=EIy,EIz=EIz,EA=EA,A=A,E=E,G=G,Kt=Kt,phi=phi,nel=nel,element=element)

    # --- Apply boundary conditions (clamped at root, free at tip)
    MMr, KKr, Tr = applyBC(MM, KK, Elem2Nodes, Nodes2DOF, BC=BC, K_root=K_root, M_root=M_root, K_tip=K_tip, M_tip=M_tip)

    # --- Compute modes and frequencies
    [Q, freq]= eig(KKr, MMr, freq_out=True)

    # --- Compute modes and frequencies
    Q = insertBCinModes(Q, Tr)
    Q, modeNames = identifyAndNormalizeModes(Q, nModes=20)

    # --- Return a dictionary
    FEM={'xNodes':xNodes, 'MM':MM, 'KK':KK, 'MMr':MMr,'KKr':KKr,'Tr':Tr,
         'Q':Q,'freq':freq, 'modeNames':modeNames}
    return FEM


# --------------------------------------------------------------------------------}
# --- Helpers, consider adding to utils 
# --------------------------------------------------------------------------------{
def rigidBodyMassMatrixAtP(m=None, J_G=None, Ref2COG=None):
    """ 
    Rigid body mass matrix (6x6) at a given reference point: 
      the center of gravity (if Ref2COG is None) 


    INPUTS:
     - m/tip: (scalar) body mass 
                     default: None, no mass
     - J_G: (3-vector or 3x3 matrix), diagonal coefficients or full inertia matrix
                     with respect to COG of body! 
                     The inertia is transferred to the reference point if Ref2COG is not None
                     default: None 
     - Ref2COG: (3-vector) x,y,z position of center of gravity (COG) with respect to a reference point
                     default: None, at first/last node.
    OUTPUTS:
      - M66 (6x6) : rigid body mass matrix at COG or given point 
    """
    # Default values
    if m is None: m=0
    if Ref2COG is None: Ref2COG=(0,0,0)
    if J_G is None: J_G=np.zeros((3,3))
    if len(J_G.flatten()==3): J_G = np.eye(3).dot(J_G)

    M66 = np.zeros((6,6))
    x,y,z = Ref2COG
    Jxx,Jxy,Jxz = J_G[0,:]
    _  ,Jyy,Jyz = J_G[1,:]
    _  ,_  ,Jzz = J_G[2,:]
    M66[0, :] =[   m     ,   0     ,   0     ,   0                 ,  z*m                , -y*m                 ]
    M66[1, :] =[   0     ,   m     ,   0     , -z*m                ,   0                 ,  x*m                 ]
    M66[2, :] =[   0     ,   0     ,   m     ,  y*m                , -x*m                ,   0                  ]
    M66[3, :] =[   0     , -z*m    ,  y*m    , Jxx + m*(y**2+z**2) , Jxy - m*x*y         , Jxz  - m*x*z         ]
    M66[4, :] =[  z*m    ,   0     , -x*m    , Jxy - m*x*y         , Jyy + m*(x**2+z**2) , Jyz  - m*y*z         ]
    M66[5, :] =[ -y*m    , x*m     ,   0     , Jxz - m*x*z         , Jyz - m*y*z         , Jzz  + m*(x**2+y**2) ]
    return M66

def LinearDOFMapping(nElem, nNodesPerElem, nDOFperNode):
    """ 
    returns the mappings from nodes to DOF and element to nodes and DOF
    for a structure with the same type of elements, assuming nodes are one after the other
    """
    nNodes = (nNodesPerElem-1)*nElem+1 # total number of nodes in system
    Nodes2DOF=np.zeros((nNodes,nDOFperNode), dtype=int)
    for i in np.arange(nNodes):
        Nodes2DOF[i,:]=np.arange(i*6, (i+1)*6) 
    Elem2DOF=np.zeros((nElem,nDOFperNode*nNodesPerElem),dtype=int)
    for i in np.arange(nElem):
        Elem2DOF[i,:]=np.concatenate((Nodes2DOF[i,:], Nodes2DOF[i+1,:]))
    Elem2Nodes=np.zeros((nElem,nNodesPerElem), dtype=int)
    for i in np.arange(nElem):
        Elem2Nodes[i,:]=(i,i+1)
    return Elem2Nodes, Nodes2DOF, Elem2DOF

def ElementDOFIndex(iel,nnel,ndof):
    """
    Compute system dofs associated with each element in one- dimensional problem
    
    INPUTS:
      DOFindex - system dof vector associated with element "iel"
      iel - element number whose system dofs are to be determined
      nnel - number of nodes per element
      ndof - number of dofs per node 
    """
    edof  = nnel*ndof            
    iStart = (iel)*(nnel-1)*ndof
    DOFindex=iStart+np.arange(0,edof)
    return DOFindex

def BuildGlobalMatrix(KK, Ke, index):
    """Assembly of element matrices into the system matrix
    INPUTS
        KK - system matrix
        Ke  - element matrix
        index - d.o.f. vector associated with an element
    """
    for i,ii in enumerate(index):
        for j,jj in enumerate(index):
            KK[ii,jj] += Ke[i,j]
    #
    #KK[index,index] += Ke
    return KK


# --------------------------------------------------------------------------------}
# --- Multi purpose assembly method 
# --------------------------------------------------------------------------------{
def cbeam_assembly(xNodes, m, EIx=None, EIy=None, EIz=None, EA=None, A=None, Kt=None, E=None, G=None, phi=None, element='frame3d',nel=None):
    """ 
    Returns the mass and stiffness FEM matrix of a beam represented with nel Frame elements 

    For uniform or straight beams, the beam is assumed to be along the x direction.
    
    NOTE: input values can be vectors or scalars.
      If they are scalars, then a beam with constant properties and of length L=xNodes is used;
      If they are vectors, values per element are required
      then linear interpolation is used. The dimension of the inputs does not need to match nel

    See also Matlab function fBeamMatrices3D_Frame6DOF
    
    INPUTS
      xNodes: define beam length, beam spanwise positions or beam nodes, either:
          -  (scalar) Beam length, for uniform beam [m]
          -  (1xn) Span vector of the beam (for straight beams) [m]
          -  (2xn) Nodes positions x,z along the beam for 2d beam [m]
          -  (3xn) Nodes positions x,y,z along the beam for 3d beam [m]

      m    : (n) Mass per length along the beam, at nodes [kg/m]

      A    : (n) Beam cross section area along the beam, at nodes [m^2]

      EIx  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]
      EIy  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]
      EIz  : (n) Elastic Modulus times Second Moment of Area of cross section, at nodes [Nm2]

      Kt  : (n) Torsion constant, at nodes [m^4]

      G   : (scalar) Shear modulus. Steel: 79.3  [Pa] [N/m^2]
      E   : (scalar) Elastic (Young) modulus

      phi : (1xn) rotation of principal axes wrt mean line (tangent) of the beam [rad], at nodes

      element: specify the element type to use along the beam: 
           'frame3d'
           'frame3dlin'
           'beam2d'

      nel  : Number of elements. If provided Structural propeties and nodes will be interpolated to match nel. 
             Otherwise, the length of xNodes determines the discretization
    
    OUTPUTS
      MM: (nDOF x nDOF)  Mass matrix
      KK: (nDOF x nDOF)  Stiffness matrix
      x : (1 x nel)   Span vector

    """
    # --- Consistency checks
    if element in ['frame3d','frame3dlin']:
        if EIx is None:
            raise Exception('For frame3d*, provide EIx')
        if EIy is None:
            raise Exception('For frame3d*, provide EIy')
        if EIz is None and (E is None or Iz is None):
            raise Exception('For frame3d*, provide EIz')
        if EA is None and (E is None or A is None):
            raise Exception('For frame3d*, provide EA')
        #if A is None:
        #    raise Exception('For frame3d*, provide A')
        #if Kt is None:
        #    raise Exception('For frame3d*, provide Kt')
        #if E is None:
        #    raise Exception('For frame3d*, provide E')
    else:
        raise NotImplementedError('Element type: {}'.format(element))

    # --- Default values
    if E is None:  E = 211e9       # Young modulus
    if G is None:  G = E/2/(1+0.3) # Young modulus
    if EIz is None: EIz=EIy
    if A is None:  A= m*0+100      # Area, TODO
    if EA is None: EA=E*A
    if Kt is None: Kt= m*0+100     # Saint Venant torsion, TODO

    if not hasattr(xNodes,'__len__'):
        xNodes=[xNodes]
    xNodes = np.asarray(xNodes)
    if len(xNodes)==1:
        xNodes0=xNodes
        # Constant beam properties
        xNodes=np.zeros((3,2))
        xNodes[0,:] =[0, xNodes0[0]]     # Beam directed about x
        EIx    = np.array([1, 1])*EIx
        EIy    = np.array([1, 1])*EIy
        EIz    = np.array([1, 1])*EIz
        EA     = np.array([1, 1])*EA 
        Kt     = np.array([1, 1])*Kt
        A      = np.array([1, 1])*A  
        m      = np.array([1, 1])*m  

    # --- Interpolate properties based on curvilinear length along the beam to get nel Elements
    # NOTE: interpolation does nothing if nel is None
    le0 = np.sqrt((xNodes[0,1:]-xNodes[0,0:-1])**2+(xNodes[1,1:]-xNodes[1,0:-1])**2+(xNodes[2,1:]-xNodes[2,0:-1])**2)
    s_span0 = np.concatenate(([0],np.cumsum(le0)))

    if nel is None:
        nel=len(m-1)
    else:
        xNodes0=xNodes
        xNodes=np.zeros((3,nel+1))
        s_span     = np.linspace(0,s_span0[-1],nel+1)
        s_span_mid = s_span[:-1]+np.diff(s_span0)/2
        xNodes[0,:] = np.interp(s_span, s_span0, xNodes0[0,:])
        xNodes[1,:] = np.interp(s_span, s_span0, xNodes0[1,:])
        xNodes[2,:] = np.interp(s_span, s_span0, xNodes0[2,:])
        if element=='frame3dlin':
            # then we interpolate at nodes
            s_span_e = s_span
        else:
            # we interpolate at element (mid-point)
            s_span_e = s_span_mid
        EIx = np.interp(s_span_e, s_span0, EIx)
        EIy = np.interp(s_span_e, s_span0, EIy)
        EIz = np.interp(s_span_e, s_span0, EIz)
        EA  = np.interp(s_span_e, s_span0, EA)
        Kt  = np.interp(s_span_e, s_span0, Kt)
        m   = np.interp(s_span_e, s_span0, m)
        A   = np.interp(s_span_e, s_span0, A)

    if element=='frame3d':
        return cbeam_assembly_frame3d(xNodes, E, G, m, EIx, EIy, EIz, Kt, EA, A, phi=None)
    else:
        raise NotImplementedError()


# --------------------------------------------------------------------------------}
# --- Assembly dedicated to frame3d (data per element)
# --------------------------------------------------------------------------------{
def cbeam_assembly_frame3d(xNodes, E, G, me, EIxe, EIye, EIze, Kte, EAe, Ae, phi=None):
    """
    Assembly a FEM model of a beam made of n elements (n+1 nodes)
    Node positions are given in 3D
    Element properties are given for each elements (n)

    INPUTS
      xNodes: (3x n+1) Nodes positions x,y,z along the beam for 3d beam [m]
      G   : (scalar) Shear modulus. Steel: 79.3  [Pa] [N/m^2]
      E   : (scalar) Elastic (Young) modulus
      me   : (n) Mass per length of elements [kg/m]
      A    : (n) Beam cross section area along the beam, for elements [m^2]
      EIy  : (n) Elastic Modulus times Second Moment of Area of cross section [Nm2]
      EIz  : (n) Elastic Modulus times Second Moment of Area of cross section [Nm2]
      EIz  : (n) Elastic Modulus times Second Moment of Area of cross section [Nm2]
      Kt   : (n) Torsion constant [m^4]
      phi : (n) rotation of principal axes wrt mean line (tangent) of the beam [rad]


      nel  : Number of elements. If provided Structural propeties and nodes will be interpolated to match nel. 
             Otherwise, the length of xNodes determines the discretization
    
    OUTPUTS
      MM: (nDOF x nDOF)  Mass matrix
      KK: (nDOF x nDOF)  Stiffness matrix
      x : (1 x nel)   Span vector
    """
    from .frame3d import frame3d_KeMe

    nElem         = len(me)        # Number of elements
    nDOFperNode   = 6              # Degrees of Freedom per Node
    nNodesPerElem = 2              # Number of nodes per element
    nNodes        = (nNodesPerElem-1)*nElem+1 # total number of nodes in system
    nDOF          = nNodes*nDOFperNode     # total system dofs

    if np.any(xNodes[1,:]!=0):
        raise NotImplementedError('Only straight beam along x supported')
    if np.any(xNodes[2,:]!=0):
        raise NotImplementedError('Only straight beam along x supported')


    # --- Coordinates system / direction cosine of each element
    DCM = elementDCMfromBeamNodes(xNodes,phi=phi)

    # --- Mapping DOF/Nodes/Elem, for consistency with advanced FEM
    Elem2Nodes, Nodes2DOF, Elem2DOF = LinearDOFMapping(nElem, nNodesPerElem, nDOFperNode)

    # --- Assembly
    MM =  np.zeros((nDOF,nDOF))
    KK =  np.zeros((nDOF,nDOF))
    # Loop on elements
    for i in np.arange(nElem):
        DOFindex=ElementDOFIndex(i,nNodesPerElem,nDOFperNode) # 1 x ndof*nnel
        DOFindex=Elem2DOF[i,:]
        #print(DOFindex)
        #print(Elem2DOF[i,:])
        P1 = xNodes[0,i]
        P2 = xNodes[0,i+1]
        Le = np.linalg.norm(P2-P1)
        Me = Le*me[i]
        # --- Element matrix
        Ke,Me,Kg = frame3d_KeMe(E,G,Kte[i],EAe[i],EIxe[i],EIye[i],EIze[i],Le,Ae[i],Me,T=0,R=None)
        # --- Build global matrices
        MM = BuildGlobalMatrix(MM, Me, DOFindex)
        KK = BuildGlobalMatrix(KK, Ke, DOFindex)

    return MM, KK, xNodes, DCM, Elem2Nodes, Nodes2DOF, Elem2DOF


# --------------------------------------------------------------------------------}
# --- Continuous Beam - Frame3d linear formulation
# --------------------------------------------------------------------------------{
def cbeam_assembly_frame3dlin(xNodes, m, Iy, Iz=None, A=None, Kv=None, E=None, G=None, phi=None):
    """
    Assemble a FEM system for a continuous beam using frame3d linear elements
    Elements are assumed to be connected continuously from 1st node to last

    xNodes: (3 x nNodes) position of the nodes.
    m     : (nNodes) linear mass per length

    phi   : rotation of principal axes wrt mean line (tangent) of the beam [rad]
    
    """
    from welib.FEM.frame3dlin import frame3dlin_KeMe
    import scipy 

    assert(xNodes.shape[0]==3)

    nNodes   = xNodes.shape[1]
    nElem    = nNodes-1
    nqe      = 12           # Number of DOF per element
    nqk      = int(nqe/2)   # Number of DOF per nodes
    nDOF_tot = nNodes*nqk   # Total number of DOF without constraint (BC)

    # --- Default values
    if Iz is None: Iz=Iy
    if E is None:  E = 211e9       # Young modulus
    if G is None:  G = E/2/(1+0.3) # Young modulus
    if A is None:  A= m*0+100      # Area
    if Kv is None: Kv= m*0+100     # Saint Venant torsion

    # --- Coordinates system / direction cosine of each element
    # Putting "z" along x
    DCM = elementDCMfromBeamNodes(xNodes,phi=phi)

    # --- Distribution of DOFs on nodes and elements
    Nodes2DOF=np.zeros((nNodes,6), dtype=int)
    for i in np.arange(nNodes):
        Nodes2DOF[i,:]=np.arange( i*6, (i+1)*6) 
    Elem2DOF=np.zeros((nElem,12),dtype=int)
    for i in np.arange(nElem):
        Elem2DOF[i,:]=np.concatenate((Nodes2DOF[i,:], Nodes2DOF[i+1,:]))
    Elem2Nodes=np.zeros((nElem,2), dtype=int)
    for i in np.arange(nElem):
        Elem2Nodes[i,:]=(i,i+1)

    # --- Element mass matrices
    Me = np.zeros((12,12,nElem))
    Ke = np.zeros((12,12,nElem))
    for ie in np.arange(nElem):
        dx= (xNodes[:,ie+1]-xNodes[:,ie]).reshape(3,1)
        le = np.linalg.norm(dx) # element length
        iNode1, iNode2 = Elem2Nodes[ie,:]
        me1 = m[iNode1]*le   # m l = rho * A * l
        me2 = m[iNode2]*le
        A1  = A[iNode1]
        A2  = A[iNode2]
        Kv1 = Kv[iNode1]
        Kv2 = Kv[iNode2]
        Iy1 = Iy[iNode1]
        Iy2 = Iy[iNode2]
        Iz1 = Iz[iNode1]
        Iz2 = Iz[iNode2]
        ke,me = frame3dlin_KeMe(E,G,Kv1,Kv2,A1,A2,Iy1,Iy2,Iz1,Iz2,le,me1,me2, R=None)
        #ke,me= frame3dlin_KeMe(me1, me2, le)
        Me[:,:,ie]=me
        Ke[:,:,ie]=ke

    # --- Assembly
    MM = np.zeros((nDOF_tot,nDOF_tot))
    KK = np.zeros((nDOF_tot,nDOF_tot))
    for ie in np.arange(nElem):
        IDOF = Elem2DOF[ie,:]
        R    = DCM[:,:,ie]
        RR   = scipy.linalg.block_diag(R,R,R,R)
        Mg   = (RR.T).dot(Me[:,:,ie]).dot(RR)
        Kg   = (RR.T).dot(Ke[:,:,ie]).dot(RR)
        MM[np.ix_(IDOF,IDOF)] += Mg
        KK[np.ix_(IDOF,IDOF)] += Kg

    return MM, KK, xNodes, DCM, Elem2Nodes, Nodes2DOF, Elem2DOF

def cbeam_frame3dlin_Kg(Tload, xNodes, Elem2Nodes, Elem2DOF, DCM, E, A, FEMmodel='frame3d_lin'):
    """ 
    Geometric stiffness due a load Tload on all the DOFs
    """
    from welib.FEM.frame3dlin import frame3dlin_Kg # TODO switch between implementation

    nDOF_tot = len(Tload)
    nElem = Elem2Nodes.shape[0]
    Kg= np.zeros((nDOF_tot,nDOF_tot))

    # --- Element mass matrices
    for ie in np.arange(nElem):
        # Going from load in global to load in local
        IDOF = Elem2DOF[ie,:]
        R    = DCM[:,:,ie]
        RR   = scipy.linalg.block_diag(R,R,R,R)
        Te   = RR.dot(Tload[IDOF])
        # Element geometrical stiffness matrix in global 
        dx = (xNodes[:,ie+1]-xNodes[:,ie]).reshape(3,1)
        L  = np.linalg.norm(dx)                         # element length
        iNode1, iNode2 = Elem2Nodes[ie,:]
        A1 = A[iNode1]
        A2 = A[iNode2]
        Kge_gl  = frame3dlin_Kg(E,A1,A2,L,Te[0],Te[6],R=DCM[:,:,ie])
        # Assembly
        Kg[np.ix_(IDOF,IDOF)] += Kge_gl
    return Kg






# --------------------------------------------------------------------------------}
# ---  
# --------------------------------------------------------------------------------{
def applyBC(MM, KK, Elem2Nodes, Nodes2DOF, BC=None, BC_root=[0,0,0,0,0,0], BC_tip=[1,1,1,1,1,1],
        M_root=None, K_root=None, Mass_root=None, COG_root=None, Inertia_root=None,
        M_tip=None, K_tip=None, Mass_tip=None, COG_tip=None, Inertia_tip=None, 
        ):
    """ 
    Apply simple boundary conditions at tip and root

    INPUTS:
      - MM, KK: (n x n) mass matrix, stiffness matrix

      - either:
          - BC: string defining the boundary condition
               'clamped-free': clamped at root, free at tip
               'free-free': free at root, free at tip
        or
           - BC_root/tip: 6-array for the BC of each DOF
             "0" = fixed
             "1" = free
             default: cantilever, root clamped and tip free

       - M_tip/root: (6x6) mass matrix to add at beam ends
       - K_tip/root: (6x6) stiffness matrix to add at beam ends

       - Mass_root/tip: (scalar) additional point mass to add at beam ends. 
                       default: None, no mass
       - COG_root/tip: (3-vector) x,y,z position of point mass wrt. the first/last node. 
                       default: None, at first/last node.
       - Inertia_root/tip: (3-vector or 3x3 matrix), diagonal coefficients or full inertia matrix
                       with respect to COG! 
                       default: None 

    OUTPUTS:
        Mr, Kr : (nr x nr) reduced mass and stiffness matrix
        Tr     : (n x nr) reduction matrix such that  Mr = Tr' MM Tr
 
    """
    if BC is not None:
        if BC=='clamped-free':
            BC_root = [0,0,0,0,0,0]
            BC_tip  = [1,1,1,1,1,1]
        elif BC=='free-free':
            BC_root = [1,1,1,1,1,1]
            BC_tip  = [1,1,1,1,1,1]


    nDOF_tot = MM.shape[0]
    # Tip and root degrees of freedom
    IDOF_root = Nodes2DOF[Elem2Nodes[0,:][0] ,:]
    IDOF_tip  = Nodes2DOF[Elem2Nodes[-1,:][1],:]

    # --- Insert tip/root inertias
    if M_root is None:
        M_root= rigidBodyMassMatrixAtP(Mass_root, Inertia_root, COG_root)
    if M_tip is None:
        M_tip = rigidBodyMassMatrixAtP(Mass_tip,  Inertia_tip, COG_tip)

    MM[np.ix_(IDOF_root, IDOF_root)] += M_root
    MM[np.ix_(IDOF_tip, IDOF_tip)]   += M_tip

    # --- Insert tip/root stiffness
    if K_root is not None:
        KK[np.ix_(IDOF_root, IDOF_root)] += K_root
    if K_tip is not None:
        KK[np.ix_(IDOF_tip, IDOF_tip)] += K_tip

    # --- Boundary condition transformation matrix (removes row/columns)
    Tr=np.eye(nDOF_tot)
    # Root BC
    IDOF_to_remove = [i for i,iBC in zip(IDOF_root, BC_root) if iBC==0]
    Tr = np.delete(Tr, IDOF_to_remove, axis=1) # removing columns
    # Tip BC
    IDOF_to_remove = [i for i,iBC in zip(IDOF_tip, BC_tip) if iBC==0]
    Tr = np.delete(Tr, IDOF_to_remove, axis=1) # removing columns

    Mr = (Tr.T).dot(MM).dot(Tr)
    Kr = (Tr.T).dot(KK).dot(Tr)
    return Mr, Kr, Tr



# --------------------------------------------------------------------------------}
# ---  
# --------------------------------------------------------------------------------{
def generalizedMassMatrix(xNodes, MM, Se):
    """ 
    Generalized mass matrix from a FEM representation when the structure is undeflected.
    xNodes: Position of the nodes (3 x nNodes)
    MM:   FEM Mass Matrix (nDOF x nDOF)
    Se:   FEM Modes (nDOF x nModes) (elastic modes, e)
    
    """
    dpn=6 # Number of DOF per nodes

    assert(xNodes.shape[0]==3)
    nDOF=MM.shape[0]

    # --- Rigid body modes (t: translation, r:rotation)
    St = np.zeros((nDOF, 3))
    Sr = np.zeros((nDOF, 3))
    for i in np.arange(xNodes.shape[1]):
        R= skew(xNodes[:,i])
        St[i*dpn   : i*dpn+3, :]= np.eye(3)
        Sr[i*dpn   : i*dpn+3, :]= -R
        Sr[i*dpn+3 : i*dpn+6, :]= np.eye(3)
    # Se: Selected modes (e:elastic)

    # --- Generalized mass matrix
    # Rigid body part             # Different Notations:
    Mtt  = (St.T).dot(MM).dot(St) # Mxx, mE
    J0   = (Sr.T).dot(MM).dot(Sr) # Mrr, Mtt, I0
    Mrt  = (Sr.T).dot(MM).dot(St) # Mrt, Mxt, mc0
    # Flexible part
    Mgt  = (Se.T).dot(MM).dot(St) # Mgt, Mgx, Mxg', Ct0
    Mgr  = (Se.T).dot(MM).dot(Sr) # Mgr, Mgt, Mtg', Cr0
    Mgg  = (Se.T).dot(MM).dot(Se) # Mgg, Me
    return Mtt, J0, Mrt, Mgt, Mgr, Mgg, St, Sr


def shapeIntegrals(xNodes, Nodes2DOF, Elem2Nodes, Elem2DOF, DCM, m, Se, Sr, Tr):
    """ 
    Compute main shape integrals from FEM implementation
    (frame3dlin for C3 for now) 

    See [2] for equations and details

    Inspired by a matlab implementation by J. Geilser:
        https://github.com/jgeisler0303/FEMBeam
    
    """
    from welib.FEM.frame3dlin import frame3dlin_Mcross

    # init
    nElem    = Elem2Nodes.shape[0]
    nNodes   = xNodes.shape[1]
    nShapes  = Se.shape[1]
    nDOF_tot = Se.shape[0]

    # --- C3 Element mass matrices
    C3 = np.zeros((3,3,12,12,nElem))
    for ie in np.arange(nElem):
        dx= (xNodes[:,ie+1]-xNodes[:,ie]).reshape(3,1)
        le = np.linalg.norm(dx) # element length
        iNode1, iNode2 = Elem2Nodes[ie,:]
        me1 = m[iNode1]*le   # m l = rho * A * l
        me2 = m[iNode2]*le
        c3 = frame3dlin_Mcross(le,me1,me2)
        C3[:,:,:,:,ie]=c3

    # --- Term for second order Cr (Mgr) terms and Oe
    # [2] (5.252) p. 233, (6.401) p. 338
    KFr= np.zeros((3,nDOF_tot,nDOF_tot))
    Kr  =np.zeros((3,nShapes,nShapes))
    for ia in np.arange(3):
        for ie in np.arange(nElem):
            lmn= [0,1,2]
            for l in np.arange(3):
                m_= lmn[1];
                n_= lmn[2];
                IDOF  = Elem2DOF[ie,:]
                R     = DCM[:,:,ie]
                RR    = scipy.linalg.block_diag(R,R,R,R)
                Gamma = DCM[:,:,ie]

                KFr[ia][np.ix_(IDOF,IDOF)] += (RR.T).dot( -C3[m_, n_,:,:,ie] + C3[n_, m_,:,:,ie]).dot(RR) * Gamma[l, ia]
                lmn= np.roll(lmn,-1) #circshift(lmn, [0 -1]);
        # [2] (6.483) p. 367
        Kr[ia,:,:]= (Se.T).dot(KFr[ia]).dot(Se)

    # --- Terms useful for 0th order of Gr, and 1st order of J
    # [2] (6.490) p. 368; (6.531) p. 379 or (6.515) p. 375
    C4= np.zeros((3, 3, nShapes))
    for l in np.arange(nShapes):
        for ia in np.arange(3):
            for ib in np.arange(3):
                C4[ia, ib, l]= -(Sr[:, ia].T).dot(KFr[ib]).dot(Se[:, l]);

    # --- 
    # (5.268) S. 237
    KFom_ab= np.zeros((3,3, nDOF_tot, nDOF_tot)) # = C6
    for ia in np.arange(3):
        for ib in np.arange(3):
            for l in np.arange(3):
                for m in np.arange(3):
                    for ie in np.arange(nElem):
                        IDOF  = Elem2DOF[ie,:]
                        R     = DCM[:,:,ie]
                        RR    = scipy.linalg.block_diag(R,R,R,R)
                        Gamma = DCM[:,:,ie]
                        if l==m:
                            m_= l+1;
                            if m_>2: m_= 0
                            n_= m_+1;
                            if n_>2: n_= 0
                            Xi= -(C3[m_, m_,:,:,ie]+C3[n_, n_,:,:,ie]) # [2] (5.266) p. 236
                        else:
                            Xi= C3[m, l,:,:,ie];
                        Madd = (RR.T).dot(Xi).dot(RR) * Gamma[l, ia]*Gamma[m, ib]
                        KFom_ab[ia, ib][np.ix_(IDOF,IDOF)] += Madd

    # --- DOF undisplaced values
    ZF0= np.zeros((nDOF_tot,1))
    for iNode in np.arange(nNodes):
        IDOF=Nodes2DOF[iNode][:3] # translational DOF only
        ZF0[IDOF,0]= xNodes[:,iNode];

    # --- [2] (5.271) p. 237
    KFom = np.zeros((6,nDOF_tot, nDOF_tot))
    Kom  = np.zeros((6,nShapes,nShapes))
    Kom0 = np.zeros((nShapes, 6))
    Kom0_= np.zeros((Tr.shape[1], 6));
    for i in np.arange(6):
        if i<3:
            KFom[i]= KFom_ab[i, i]
        else:
            a= i-3;
            b= a+1;
            if b>2: b= 0
            KFom[i]= KFom_ab[a, b] + KFom_ab[a, b].T
        Kom[i]= (Se.T).dot(KFom[i]).dot(Se);
        Kom0 [:, i]= (Se.T).dot(KFom[i]).dot(ZF0).ravel()
        Kom0_[:, i]= (Tr.T).dot(KFom[i]).dot(ZF0).ravel()

    return C3, Kr, C4, KFom_ab, Kom, Kom0, Kom0_ 


def geometricalStiffening(xNodes, Kinv, Tr, Se, Nodes2DOF, Elem2Nodes, Elem2DOF, DCM, E, A, Kom0_=None, Ct0_=None):
    """ 
    Axial stiffening terms
    See [2] 6.330 S. 319
    
    """
    def geo_stiff_wrap(Tload):
        return cbeam_frame3dlin_Kg(Tload, xNodes, Elem2Nodes, Elem2DOF, DCM, E, A)

    nDOF_tot = Kinv.shape[0]
    nNodes   = Nodes2DOF.shape[0]
    iMaxDim = np.argmax(np.max(np.abs(xNodes),axis=1)-np.min(np.abs(xNodes),axis=1)) 

    # Stiffness from tip load
    Fend_ax = np.zeros((nDOF_tot, 1))
    iNode=nNodes-1 # Load node
    DOF=Nodes2DOF[iNode,:]
    Fend_ax[DOF[iMaxDim], 0]= 1 # Unit loads at tip
    
    # All axial stiffening contributions
    GKg=dict()
    GKg['Fend'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Fend_ax))                 ).dot(Se)
    GKg['t_ax'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Ct0_[:, iMaxDim])))).dot(Se)
    GKg['omxx'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 0])))     ).dot(Se) 
    GKg['omyy'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 1])))     ).dot(Se) 
    GKg['omzz'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 2])))     ).dot(Se) 
    GKg['omxy'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 3])))     ).dot(Se) 
    GKg['omxz'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 4])))     ).dot(Se) 
    GKg['omyz'] = (Se.T).dot( geo_stiff_wrap( -Kinv.dot(Tr.dot(Kom0_[:, 5])))     ).dot(Se) 

    return GKg


# TODO verify that these are DCM and not the transpose
def elementDCMfromBeamNodes(xNodes, phi=None):
    """ Generate element Direction cosine matricse (DCM) 
    from a set of ordered node coordinates defining a beam mean line

    INPUTS:
        xNodes: 3 x nNodes
        phi (optional): nNodes angles about mean line to rotate the section axes
    OUTPUTS:
        DCM:  3 x 3 x (nNodes-1)
    """
    def null(a, rtol=1e-5):
        u, s, v = np.linalg.svd(a)
        rank = (s > rtol*s[0]).sum()
        return v[rank:].T.copy()

    assert(xNodes.shape[0]==3)
    nElem=xNodes.shape[1]-1
    DCM = np.zeros((3,3,nElem))
    for i in np.arange(nElem):
        dx= (xNodes[:,i+1]-xNodes[:,i]).reshape(3,1)
        le = np.linalg.norm(dx) # element length
        e1 = dx/le # tangent vector
        if i==0:
            e1_last = e1
            e2_last = null(e1.T)[:,0].reshape(3,1) # x,z-> y , y-> -x 
        # normal vector
        de1 = e1 - e1_last
        if np.linalg.norm(de1)<1e-8:
            e2 = e2_last
        else:
            e2 = de1/np.linalg.norm(de1)
        # Rotation about e1
        if phi is not None:
            R  = np.cos(phi[i])*np.eye(3) + np.sin(phi[i])*skew(e1) + (1-np.cos(phi[i]))*e1.dot(e1.T);
            e2 = R.dot(e2)
        # Third vector
        e3=np.cross(e1.ravel(),e2.ravel()).reshape(3,1)
        DCM[:,:,i]= np.column_stack((e1,e2,e3)).T;
        e1_last= e1
        e2_last= e2
    return DCM



# --------------------------------------------------------------------------------}
# --- Mode tools 
# --------------------------------------------------------------------------------{
def modeNorms(q, iDOFstart=0, nDOF=6):
    """ 
    Return norms of components of a mode
    Norm is computed as sum(abs())
        q: mode vector
        iDOFStart: where to start in mode vector
        nDOF: number of DOF per node typically 6 for 3D and 2/3 for 2D
    """
    MaxMag=np.zeros(nDOF)
    for i in np.arange(nDOF): 
        MaxMag[i] = np.sum(np.abs(q[iDOFstart+i::nDOF]))
    return MaxMag

def normalize_to_last(Q, Imodes, iDOFStart=0, nDOF=6):
    for iimode, imode in enumerate(Imodes):
        mag = modeNorms(Q[:,imode], iDOFStart, nDOF)[:int(nDOF/2)]
        iMax= np.argmax(mag);
        v_= Q[iDOFStart+iMax::nDOF, imode];
        Q[:, imode]= Q[:, imode]/v_[-1]
    return Q

def orthogonalizeModePair(Q1, Q2, iDOFStart=0, nDOF=6):
    # Find magnitudes to see in which direction the mode is the most
    mag = modeNorms(Q1, iDOFStart, nDOF)[:int(nDOF/2)]
    idx= np.argsort(mag)[-1::-1]
    k11 = sum(Q1[iDOFStart+idx[0]-1::nDOF]);
    k12 = sum(Q1[iDOFStart+idx[1]-1::nDOF]);
    k21 = sum(Q2[iDOFStart+idx[0]-1::nDOF]);
    k22 = sum(Q2[iDOFStart+idx[1]-1::nDOF]);
    Q1_ = k11*Q1 + k21*Q2
    Q2_ = k12*Q1 + k22*Q2
    return Q1_, Q2_

def insertBCinModes(Qr, Tr):
    """
    Qr : (nr x nr) reduced modes
    Tr : (n x nr) reduction matrix such that  Mr = Tr' MM Tr
    """
    return Tr.dot(Qr)

def identifyAndNormalizeModes(Q, nModes=None, element='frame3d'):
    """ 
    Attempts to identify and normalized the first `nModes` modes
    Modes are normalized by last values unless this value is too small compared to the max
    in which case the max is used.
    Mode names are returned of the form [u,v][x,y,z][n]
      where "u": displacements, "v": slopes, and "n" is the mode number in that direction
    """
    if nModes is None: nModes=Q.shape[1]
    if element in ['frame3d','frame3dlin']:
        nDOF=6
        sDOF=['ux','uy','uz','vx','vy','vz']

    cDOF=np.zeros(nDOF,dtype=int) # Counter on Modes in each DOF
    modeNames=[]

    for i in np.arange(nModes):
        q=Q[:,i]
        mag = modeNorms(q, iDOFstart=0, nDOF=nDOF)
        idx= np.argsort(mag)[-1::-1]
        iMax = idx[0]
        U = Q[iMax::nDOF,i]
        # Detect rigid body mode (0 or NaN frequencies), component constant and non-zero
        rigid=False
        for idof in np.arange(nDOF):
            Ui = Q[idof::nDOF,i]
            Umax  = max(abs(Ui))
            if Umax>1e-6:
                if len(np.unique(np.around(Ui/Umax,3)))==1:
                    icst=idof
                    rigid=True
                    break
        # Mode name
        if rigid:
            mode_name =sDOF[iMax]+'_'+sDOF[icst]+'_rigid'
        else:
            cDOF[iMax]+=1
            mode_name = sDOF[iMax]+str(cDOF[iMax])
        modeNames.append(mode_name)

        #if sDOF[iMax] in ['vy','vz']:
        #    print('Mode {} has strong slope, double check identification'.format(i))
        #print('>>>Mode',i, 'name:',mode_name, mag)

        # Normalization by max or last
        Umax  = max(abs(U))
        Ulast = abs(U[-1])
        if Ulast*100< Umax: # some tuning factor if last is close to 0
            # Normalize by max
            fact = Umax*np.sign(U[-1])
        else:
            # Normalize by last
            fact = Ulast*np.sign(U[-1])
        Q[:,i]= Q[:,i]/fact
    return Q, modeNames








# --------------------------------------------------------------------------------}
# ---  
# --------------------------------------------------------------------------------{
if __name__=='__main__':
    pass
