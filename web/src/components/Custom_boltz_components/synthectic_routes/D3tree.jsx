
import { ArrowBackOutlined, ArrowForwardOutlined, ArrowRightOutlined, CancelOutlined, CloseOutlined, Download } from "@mui/icons-material";
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Accordion, AccordionDetails, AccordionSummary, Alert, AppBar, Button, CardActions, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControl, Grid, IconButton, LinearProgress, Paper, Select, Snackbar, Stack, Tab, Table, TableHead, TableBody, TableCell, tableCellClasses, TableContainer, TableRow, Tabs, TextField, Toolbar, Tooltip, Typography } from "@mui/material";
import Card from '@mui/material/Card';
import MenuItem from '@mui/material/MenuItem';
import { useTheme } from "@mui/material/styles";






import Apollo from '../assets/Vendorlogos/apollo-scientific-logo.png';
import Chembl from '../assets/Vendorlogos/chembllogopng.png';
import Chemdiv from '../assets/Vendorlogos/chemdivlogo.webp';
import Chemspace from '../assets/Vendorlogos/chemspace.png';
import emol from '../assets/Vendorlogos/emollogo.png';
import Lifechemicals from '../assets/Vendorlogos/lifechemicals.png';
import Mculelogo from '../assets/Vendorlogos/mculelogo.png';
import Otava from '../assets/Vendorlogos/otava_logo.png';
import Vitasm from '../assets/Vendorlogos/vitasmlablogo.png';

import Tree from "react-d3-tree";
import { useLocation, useNavigate } from "react-router";
// import { useWebSocket } from 'socketup';
// import { useToken } from "tokenfetch";
import MainCard from "../cards/MainCard";
import './d3tree.css';
// import DwnPdf, { Downpdf, DwnSVG } from "./Download";
import styled from "@emotion/styled";
import ArrowBackIosRoundedIcon from '@mui/icons-material/ArrowBackIosRounded';
import ArrowForwardIosRoundedIcon from '@mui/icons-material/ArrowForwardIosRounded';
import { Box } from "@mui/system";
// import { useSnackbar } from 'components/experimentAlerts/ExperimentAlerts';
// import { useSubmitLoader } from "components/submitloaders/SubmitLoaders";
import { useEffect, useRef, useState } from "react";
// import { Arrayupdate, DocfetchMultiAPI, EXPsubmitMultiAPI3 } from 'services/servfunctions';
import Subappbar from "../cards/Subappbar";
// import { useUser } from "user";
import ExampleCanvas from "./RDkit/ExampleCanvas";
import { useCenteredTree, useCenteredTree2 } from "./helpers";
// import CollaboratorComp from "ui-component/subappbar/collaboratorcomponent";
// import Condition_Comp from "./condition_component";
// import { nodejsapi } from "config";
// import { useCredits } from 'contexts/CreditsContext';

//tree node styling
const containerStyles = {
    width: "100%",
    minWidth: "100%",
    height: '70vh',
    display: 'block',
    margin: 'auto'
};



/// template free tree


// template based tree
const renderForeignObjectNode = ({
    nodeDatum,
    foreignObjectProps,
    referenceProps,
    handlereferencedialog,
    handlesmilesCopysnack,
    handlenodedialog,
    ColorButton,
    handleintermdialog,
    handleCheckbox,
    checkboxstate,
    setcheckboxalertdialog,
    setSharexpdialog,
    previw,
    treeobj,
    Agsc,
    UID,
    currentUser
}) => (
    <>
        {

            (nodeDatum.reference == "False") ?
                <>
                    <foreignObject {...foreignObjectProps}>
                        <Card sx={{ backgroundColor: 'whitesmoke', border: `4px solid ${nodeDatum.color}` }} raised={true}>
                            {/*  Copy smiles tool tip  */}
                            <Tooltip title='copy Smiles' >
                                <ContentCopyRoundedIcon sx={{ opacity: '0.1', fontSize: '1.25rem', position: 'absolute', left: '163px', WebkitAppearance: 'none', }}
                                    onClick={() => {
                                        navigator.clipboard.writeText(`${nodeDatum.smile}`);
                                        handlesmilesCopysnack();
                                    }} />
                            </Tooltip>
                            <div onClick={(nodeDatum.id == 0) ? () => { } : () => { handlenodedialog({ smile: nodeDatum.smile, building_block_path: nodeDatum.building_block_path, score: nodeDatum.sascore, pubchem_hazards: nodeDatum.pubchem_hazards }) }}>

                                <ExampleCanvas
                                    onClick={(nodeDatum.id == 0) ? () => { alert('not valid') } :
                                        () => handlenodedialog({
                                            smile: nodeDatum.smile,
                                            uspto_link: nodeDatum.uspto_link,
                                            usid: nodeDatum.usid,
                                            building_block_path: nodeDatum.building_block_path,
                                            score: nodeDatum.sascore,
                                            pubchem_hazards: nodeDatum.pubchem_hazards
                                        })
                                    }
                                    structure={nodeDatum.smile} />
                            </div>
                        </Card>

                    </foreignObject>

                </>
                :
                <foreignObject {...referenceProps}>
                    {
                        ((UID.scores == 'true' || UID.scores == undefined) && !Agsc) && <Button
                            variant="outlined"
                            sx={{
                                WebkitAppearance: 'none',
                                backgroundColor: 'whitesmoke',
                                color: "#323259",
                                borderColor: "#323259",
                                '&:hover': {
                                    backgroundColor: 'whitesmoke',
                                }
                            }}
                            onClick={() => {

                                const reactants = []
                                nodeDatum.children.map((data) => {
                                    reactants.push(data.smile)
                                })
                                const reaction = `${reactants.join('.')}>>${nodeDatum.smile}`

                                handlereferencedialog({
                                    title: nodeDatum?.title,
                                    route_score: nodeDatum?.route_score,
                                    rxn_score: nodeDatum?.rxn_score,
                                    procedure: nodeDatum?.procedure,
                                    usid: nodeDatum?.usid,
                                    conditions: nodeDatum.conditions,
                                    atom_economy: nodeDatum?.atom_economy?.toFixed(4),
                                    reaction_class: nodeDatum?.reaction_class,
                                    reaction_name: nodeDatum?.reaction_name,
                                    yield: nodeDatum?.yield?.toFixed(4),
                                    fwd_score: nodeDatum?.fwd_score,
                                    uspto_link: nodeDatum?.uspto_link,
                                    reaction: reaction,
                                    pathid: treeobj,
                                    nodeid: nodeDatum?.id,
                                    template_relev_score: nodeDatum?.template_relev_score,
                                    forward_scores: nodeDatum?.forward_scores,
                                    scores: nodeDatum?.scores,
                                    fwd_feas_probs: nodeDatum?.fwd_feas_probs,
                                    reaction_yield: nodeDatum?.reaction_yield,
                                    rebolt_score: nodeDatum?.rebolt_score
                                })
                            }
                            }
                        >
                            Reference
                        </Button>
                    }
                </foreignObject>

        }

    </>
);

    const StyledTableCell = styled(TableCell)(({ theme }) => ({
        [`&.${tableCellClasses.head}`]: {
            color: "#323259",
        },
        [`&.${tableCellClasses.body}`]: {
            fontSize: 14,
        },
    }));

    const StyledTableRow = styled(TableRow)(({ theme }) => ({
        '&:nth-of-type(odd)': {
        },
        // hide last border
        '&:last-child td, &:last-child th': {
            border: 0,
        },
    }));


    const ColorButton = styled(Button)(({ theme }) => ({
        color: 'white',
        backgroundColor: '#501f84',
        '&:hover': {
            backgroundColor: '#7030b3',
        },
    }));

    const ColorButton2 = styled(Button)(({ theme }) => ({
        color: 'white',
        backgroundColor: "black",
        '&:hover': { backgroundColor: '#000000bd' }
    }));
    const DelButton = styled(Button)(({ theme }) => ({
        color: 'white',
        backgroundColor: "red",
        '&:hover': { backgroundColor: '#ff0000a8' }
    }));


export default function D3tree({
    Data,
    Uid = {},
    cpath = 0,
    viewall = false,
    Msg = '',
    cluster = false,
    clusterNUM = [],
    currentCluster = 0,
    Procedurepath = [],
    viewclusterpaths = () => {},
    Agsc = false,
    eid = '',
    template = 'retrosynthesis',
    pid = '',
    Currentpathfun = () => {},
    Tabval = 'pathways',
    viewpathways = () => {},
    userRole = '',
    Preview = false
}) {
    {/*set tree translation */ }
    const [translate, containerRef] = useCenteredTree();
    const [translate2, containerRef2] = useCenteredTree2();
    const [treezoom, settreezoom] = useState(true);
    {/*data storage */ }
    const [referencedata, setReferenceData] = useState([]);
    const [nodedialogdata, setNodedialogData] = useState([]);
    const [Vendorsdata, setVendorsdata] = useState([])
    const [Pathsfound, setPathsfound] = useState('')
    {/*main tree output */ }
    {/*dialogs */ }
    const [referencedialog, setReferencedialog] = useState(false);
    const [refusid, setrefusid] = useState([])
    const [reftitle, setreftitle] = useState([])
    const [refprocedure, setrefprocedure] = useState([])
    const [reflink, setreflink] = useState([])
    const [refdialog, setrefdialog] = useState(false)
    const [X, setX] = useState('')
    const [nodedialog, setnodedialog] = useState(false);
    const [intermdialog, setIntermdialog] = useState(false);
    const [advancedsearch, setAdvancedsearch] = useState(5);
    const [Dwndiag, setDwndiag] = useState(false)
    {/*massionary */ }
    const [intermsmile, setIntermsmile] = useState('');
    const [experimentname, setExperimentname] = useState('');
    const [buttonloading, setButtonloading] = useState(false);
    const [buttonloading2, setButtonloading2] = useState(false);
    {/*setinterm update object */ }
    const [treeobj, settreeobj] = useState({});
    const [checkboxstate, setCheckboxstate] = useState(null);
    const [updateobject, setUpdateobject] = useState({});
    const [inrespid, setinrespid] = useState('');
    const [intermoutput, setintermoutput] = useState([]);
    const [intermdocid, setinterdocid] = useState('')
    const [ShowmoreRoutes, setShowmoreRoutes] = useState(false)
    const [Pnodeid, setPnodeid] = useState('')
    const [runupdate, setrunupdate] = useState(false)
    const [previw, setPreviw] = useState(false)
    const [saveAlert, setsaveAlert] = useState(false)
    const [Minimize, setMinimize] = useState(false)
    const [intermpathno, setintermpathno] = useState('')

    {/*path count */ }
    // const [sampledata, setSampledata] = useState({});
    const [pathcount, setPathcount] = useState(0);
    const [pathdata, setPathdata] = useState([]);
    const [incrementbuttonstate, setincrementbuttonstate] = useState(false)
    // const [sampledataref, setSampledataref] = useState();

    {/*share experiments */ }
    const [ShareExpdialog, setSharexpdialog] = useState(false)
    const [projectsData, setprojectsData] = useState([])
    const [age, setAge] = useState('')
    const [project, setproject] = useState({})
    const [alertinit, setalertinit] = useState(false);
    const [Sexperimentname, setSexperimentname] = useState('');
    const [Sexperimentsnack, setSexperimentsnack] = useState(false)
    const [UID, setUID] = useState('')
    const [MSG, setMSG] = useState('')
    const [nodeTab, setnodeTab] = useState('Buy')
    const [reftab, setreftab] = useState('scores')
    const [Scorereqsend, setScorereqsend] = useState(false)
    const [Energyvalue, setEnergyvalue] = useState({})
    const [clusterval, setclusterval] = useState(null)
    const [ElNopen, setELNopen] = useState(false)
    const [ELNdata, setELNdata] = useState({ name: '', description: '' })
    const [showErrMsg, setshowerrMsg] = useState(false)
    const [errorMsg, setErrorMsg] = useState('')
    const [ELNPATH, setELNPATH] = useState({})
    const [Elsnack, setElsnack] = useState(false)
    const [currentUser, setcurrentUser] = useState({})


    {/*snack bar state*/ }
    const [savesnackstate, setsavesnackstate] = useState(false)
    const [experimentnamedialog, setexperimentnamedialog] = useState(false)
    const [smilesCopysnack, setsmilesCopysnack] = useState(false)
    {/*progress */ }
    const [progress, setprogress] = useState(false);
    const [checkboxalertdialog, setcheckboxalertdialog] = useState(false);
    const theme = useTheme()
    const navigate = useNavigate()
    // const { eid, template, pid, idx } = useParams();
    const location = useLocation();
    const nodeSize = { x: 190, y: 180 };
    const nodeSize2 = { x: 190, y: 180 }
    const foreignObjectProps = {
        width: nodeSize.x,
        height: nodeSize.y,
        x: -80,
        y: -17,
    };
    const foreignObjectProps2 = {
        width: nodeSize2.x,
        height: nodeSize2.y,
        x: -80,
        y: -10,
    };
    const referenceProps = {
        width: nodeSize.x,
        height: nodeSize.y,
        margin: '10px',
        x: -50,
        y: 70,
    };
    const referenceProps2 = {
        width: nodeSize2.x,
        height: nodeSize2.y,
        x: -120,
        y: -45,
    };

    const iconstyles = {
        color: 'white'
    }
    const iconstyle2 = {
        color: "#323259"
    }
    const iconstyle3 = {
        color: "#323259",
        padding: '2px'
    }

    const tokenid = ''

    const hazardcellstyle = {
        fontSize: "10px !important",
    }

    const pubchem_hazards = {
        "H300 (74.1%)": {
            "message": " Fatal if swallowed [Danger Acute toxicity, oral]",
            "Hazard Class": "Acute toxicity, oral"
        },
        "H315 (83.3%)": {
            "message": " Causes skin irritation [Warning Skin corrosion/irritation]",
            "Hazard Class": "Skin corrosion/irritation"
        },
        "H318 (74.1%)": {
            "message": " Causes serious eye damage [Danger Serious eye damage/eye irritation]",
            "Hazard Class": "Serious eye damage/eye irritation"
        },
        "H335 (74.1%)": {
            "message": " May cause respiratory irritation [Warning Specific target organ toxicity, single exposure; Respiratory tract irritation]",
            "Hazard Class": "Specific target organ toxicity, single exposure; Respiratory tract irritation"
        }
    }

    const closeReferenceDialog = () => {
        setReferencedialog(false);
        setrefdialog(false);
        setreftab('scores');
        setReferenceData([]);
        setrefusid([]);
        setreflink([]);
        setrefprocedure([]);
        setreftitle([]);
        setEnergyvalue({});
    };


    const intermpathRef = useRef('');








    {/*get unique token function*/ }

    const handlereferencedialog = ({ ...data }) => {
        setReferencedialog(true);
        setReferenceData([{ ...data }]);
        setrefusid([...data.usid].slice(0, 50))
        setreflink([...data.uspto_link.slice(0, 50)])
        setrefprocedure([...data.procedure.slice(0, 50)])
        setreftitle([...data.title.slice(0, 50)])

    }
    const handlenodedialog = ({ ...data }) => {
        setnodedialog(true)
        setNodedialogData([{ ...data }])
        if (template == 'retrosynthesis') {
            if (data.building_block_path != "None") {
                setVendorsdata([...data.building_block_path])
            }
        }
        else {
            if (data.building_block_path != "None") {
                setVendorsdata([...data.building_block_path])
            }
        }
    }







    const handleintermdialog = ({ smile, nodeid }) => {
        setIntermdialog(true)
        setIntermsmile(smile)
        setPnodeid(nodeid)
    }
    const handlezoom = () => {
        settreezoom(!treezoom)
    }
    const handleCheckbox = (data) => {
        setCheckboxstate(data);
    }

    const handlesmilesCopysnack = () => {
        setsmilesCopysnack(true);
    }



    const setUserdetails = () => {
        let user = userDetails?.userdetails

        if (user) {
            setcurrentUser(user)
        }
    }


    const fetchJsonFile = async () => {
        let paths = Data;
        if (typeof Data === 'string') {
            try {
                let pathObject = JSON.parse(Data);
                paths = Object.values(pathObject);
                settreeobj(paths[0])
            } catch {
                paths = [];
            }
        }

        if (Array.isArray(paths)) {
            paths = [...paths].sort((a, b) => (a.idx ?? 0) - (b.idx ?? 0));
        } else if (paths && typeof paths === 'object') {
            paths = [paths];
        } else {
            paths = [];
        }

        // if (Tabval == 'pathways') {
            if (paths.length > 0) {
                setPathdata(paths)
                if (pathdata.length == 1) {
                    setincrementbuttonstate(true)
                }
                if (paths[cpath] != undefined) {
                    setPathcount(cpath)
                    settreeobj(paths[cpath])
                }
                else {
                    setPathcount(0)
                    settreeobj(paths[0])
                }
                setButtonloading(false)
            }
        // }
        // else {
        //     if (Procedurepath?.length > 0) {
        //         setPathdata(Procedurepath.sort((a, b) => a.idx - b.idx))
        //         if (pathdata.length < 2) {
        //             setincrementbuttonstate(false)
        //         }
        //         setPathcount(0)
        //         settreeobj(Procedurepath[0])
        //         setButtonloading(false)
        //     }
        // }

    }



    useEffect(() => {
        setUID(Uid)
        void fetchJsonFile()
    }, [Data])


    const UpdateInfo = async () => {
        await DocfetchMultiAPI({ apisubstring: 'retrosynthesis', Docid: eid, token: tokenid }).then((dat) => {
            let data = dat.data
            setUID(dat.data)
        })
    }



    const getref = async () => {
        setButtonloading(true)
        setUID(Uid)
        fetchJsonFile()
    }


    const getlocationdata = () => {
        if (location?.state?.path) {
            setUID({ uid: location.state.uid })
            setPathcount(location.state.path.idx)
            getref()
        } else {
            // getExperimentoutput();

            getref()
        }
    }



    const incrementfun = () => {

        if (pathdata.length < 1) {
            setincrementbuttonstate(true)
        } else {
            let len = pathdata.length - 1
            if (pathcount < len || pathcount == 0) {
                let inc = pathcount + 1
                setPathcount(pathcount + 1)
                settreeobj(pathdata[inc])
                Currentpathfun(inc)
            }
        }
    }
    const decrementfun = () => {

        if (pathcount > 0) {
            if (pathdata.length < 1) {
                setincrementbuttonstate(true)
            }
            setPathcount(pathcount - 1)
            let inc = pathcount - 1
            settreeobj(pathdata[inc])
            Currentpathfun(inc)
        }
    }



    // get intermediet output
    // const getintermoutput = async (resid) => {
    //     await DocfetchMultiAPI({ apisubstring: 'intermediates', Docid: resid, token: tokenid }).then(
    //         (doc) => {
    //             setintermoutput([{
    //                 outputFilePath: doc?.data?.outputFilePath,
    //                 id: doc.data._id,
    //                 status: doc.data.status,
    //                 target_mol: doc.data.target_mol,
    //                 parentnodeid: doc.data.parentnodeid,
    //                 pathid: doc.data.pathid
    //             }]);
    //         })
    // }

    // submit intermsmile
    // const submitIntermsmile = async () => {
    //     const project =
    //         UID?.project && Object.keys(UID.project).length > 0
    //             ? UID.project
    //             : {
    //                 pid: userDetails?.user.userdata?.project?._id,
    //                 name: userDetails?.user.userdata?.project?.name
    //             };

    //     const approved = await deductCredits({ project: project, tool: "Intermediate_path" })

    //     if (!approved || approved.error) {
    //         return
    //     }
    //     showSubmissionDialog()

    //     setintermoutput([])


    //     let Data = {
    //         Apidata: {
    //             "target_mol": intermsmile,
    //             "single_step": "true",
    //             "max_steps": 5,
    //             "yield": "Yield",
    //             "mode": "all",
    //             "custom_starting_materials": "false",
    //             "file_path": ['none'],
    //             "cas": "false",
    //             "cas_no": "",
    //             "exclude_toxic": "false",
    //             "custom_toxic_materials": "false",
    //             "custom_toxic_materials_path": ""
    //         },
    //         DocData: {
    //             type: "intermediates",
    //             target_mol: intermsmile,
    //             max_steps: advancedsearch,
    //             experimentName: UID.name,
    //             project: UID.project,
    //             single_step: true,
    //             experiment_id: eid,
    //             status: 'pending',
    //             uid: UID.uid,
    //             pathid: `${treeobj.idx}`,
    //             parentnodeid: `${Pnodeid}`
    //         }
    //     }


    //     await EXPsubmitMultiAPI3({ completeddata: Data, job_name: 'intermediates', creditsToFreeze: approved?.deductcredits, apisubstring: 'intermediates' })
    //         .then(async (res) => {
    //             setinrespid(res.docId);
    //             getintermoutput(res.docId)
    //             intermpathRef.current = res.docId
    //         })
    //         .then(() => {
    //             setIntermsmile('')
    //             hideSubmissionDialog()
    //         })
    //     setTimeout(() => {
    //         setIntermdialog(false);
    //     }, 3000);
    // }


    // const updateFinalsave = (data) => {
    //     setButtonloading2(true)
    //     let ids = [Pnodeid]
    //     let mainArray = [data]
    //     const childrentest = false
    //     mainArray
    //         .forEach(
    //             function iter(a) {

    //                 if (ids.includes(`${a.id}`)) {
    //                     a.children = updateobject.children;
    //                     a.disabled = !childrentest
    //                 } else {
    //                     a.disabled = !childrentest
    //                     Array.isArray(a.children) && a.children.forEach(iter);
    //                 }
    //             }
    //         );
    //     settreeobj({ ...treeobj, path: { ...mainArray[0] } });
    //     setrunupdate(false)
    //     setUpdateobject({})
    //     setTimeout(() => {
    //         setButtonloading2(false)
    //     }, 3000)
    //     // setPreviw(true)
    // }

    // useEffect(() => {
    //     if (runupdate) {
    //         updateFinalsave(treeobj.path)
    //     }
    // }, [updateobject])

    // const handleupdateobject = ({ data, parid, pathid }) => {

    //     if (pathid == treeobj.idx.toString()) {
    //         setPnodeid(parid)
    //         setUpdateobject({})
    //         let dataupdateobject = [{ ...data }]
    //         dataupdateobject
    //             .forEach(
    //                 function iter2(a) {
    //                     a.id = uniqid()
    //                     Array.isArray(a.children) && a.children.forEach(iter2);
    //                 }
    //             );
    //         setrunupdate(true)
    //         setUpdateobject({ ...dataupdateobject[0] })
    //     }
    //     else {
    //         setcheckboxalertdialog(true)
    //     }

    // }



    // const EBfunction = async (reaction) => {
    //     setScorereqsend(true)
    //     await axios.post('https://energybarrier.boltzmann.co/ReactionBarrierPrediction',
    //         {
    //             mode: "cyclo",
    //             experiment_id: eid,
    //             tokenid: tokenid,
    //             rxn_smile: reaction
    //         }
    //     ).then((response) => {
    //         setEnergyvalue(response.data[0])
    //         setScorereqsend(false)
    //     })
    // }

    // const proreqsubmit = async () => {

    //     const approved = await deductCredits({ project: UID.project, tool: "procedure" })
    //     if (!approved) {
    //         return
    //     }

    //     showSubmissionDialog()
    //     try {

    //         let completeddata = {
    //             job_name: "Procedure_request",
    //             experimentData: {
    //                 "experiment_id": eid,
    //                 "tokenid": tokenid,
    //                 "retro_flow": "tb",
    //                 "pathway_idx": treeobj.idx,
    //                 "path": {}
    //             },
    //             creditsToFreeze: approved?.deductcredits
    //         }

    //         await axios.post(`${nodejsapi}/addDocRebolt`, { senddata: completeddata, creditsToFreeze: approved?.deductcredits, estimated_time: approved?.estimated_time }, { withCredentials: true });
    //         hideSubmissionDialog()
    //         showSnackbar('Procedure request submitted', 'success')
    //     }
    //     catch (err) {
    //     }

    // }

    const ProcedureReq = ({ pathinfo, pathid }) => {
        if (pathinfo.paths_pro_req != undefined) {
            const pathReq = pathinfo.paths_pro_req
            const PathAvail = pathinfo.paths_pro_available
            if (pathReq.includes(pathid) && !PathAvail.includes(pathid)) {
                return (
                    <Typography sx={{ marginLeft: '10px', color: 'orange !important' }}>Requested</Typography>
                )
            }
            else if (pathReq.includes(pathid) && PathAvail.includes(pathid)) {
                return (
                    <Typography sx={{ marginLeft: '10px', color: 'green !important' }}>Available</Typography>
                )
            }
            else {
                return <Button size='small' onClick={proreqsubmit} sx={{ marginLeft: '10px' }} color='secondary' variant='outlined'>Request</Button>
            }
        }
    }



  console.log("treeobj", treeobj.path)
    



    // useEffect(() => {
    //     getref()
    //     setclusterval(currentCluster)
    // }, [Data, Tabval, Procedurepath])


   

   



    

    
    return (
        <>

            <Grid container spacing={2}>
                <Grid item xl={(intermoutput.length > 0 && Minimize == false) ? 8 : 12} md={(intermoutput.length > 0 && Minimize == false) ? 6 : 12} style={{ transition: 'ease-in-out', width: '100%' }} sm={12} xs={12}>
                    <MainCard sx={{ position: 'sticky', top: '90px', display: 'block', width: '100%' }}>
                        {/* <AppBar position="static" sx={{ margin: '0px', backgroundColor: 'white' }}>
                            <Toolbar variant="dense" sx={{ display: 'flex', verticalAlign: 'center' }}>
                                <Box sx={{ flexGrow: '1', textAlign: 'center' }}>
                                    {
                                        cluster &&
                                        <FormControl sx={{ width: '200px' }}>
                                            <Select
                                                labelId="demo-simple-select-label"
                                                id="demo-simple-select"
                                                value={clusterval}

                                                MenuProps={{
                                                    PaperProps: {
                                                        style: {
                                                            height: 200,
                                                            borderBottomLeftRadius: 10,
                                                            borderBottomRightRadius: 10
                                                        },
                                                    },
                                                }}
                                                size='small'
                                                onChange={(event) => {
                                                    viewclusterpaths(0, Number(event.target.value))
                                                }}
                                            >
                                                {clusterNUM.map((data) =>
                                                    <MenuItem value={data}>{`Cluster ${data}`}</MenuItem>
                                                )}

                                            </Select>
                                        </FormControl>}
                                </Box>


                                <Tooltip title="save experiment">

                                    {/* <IconButton
                                        size="small"
                                        color="secondary"
                                        variant="contained"
                                        onClick={
                                            () =>{
                                                //  savetree()
                                                }}
                                        disabled={Object.keys(treeobj).length > 0 ?  false:true}
                                    >
                                        <Save  sx={iconstyle2} />
                                    </IconButton> */}
                                {/* </Tooltip>
                                <Tooltip title='Download'>
                                    <IconButton
                                        size="small"
                                        color="secondary"
                                        variant="contained"
                                        onClick={() => { setDwndiag(true) }}
                                        disabled={treeobj ? Object.keys(treeobj)?.length != 0 ? false : true : true}

                                    >
                                        <Download sx={iconstyle2} />
                                    </IconButton>
                                </Tooltip>
                                <CollaboratorComp collection={'retrosynthesis'}
                                    collabs={Uid?.sharedTo || []}
                                    id={Uid._id}
                                    project={Uid.project}
                                    userRole={userRole}
                                />
                            </Toolbar>
                        </AppBar> */}
                        {(treeobj && Object.keys(treeobj)?.length != 0) &&
                            <div style={{ containerStyles }}>

                                <Tooltip title='previous path'>
                                    <IconButton sx={pathcount < 1 ? { visibility: 'hidden' } : { visibility: 'visible' }} onClick={() => decrementfun()} ><ArrowBackOutlined sx={iconstyle2} /></IconButton>
                                </Tooltip>
                                <Typography variant='subtitle1' sx={{ display: 'inline-block', ...iconstyle2 }} >Path : {Tabval != 'pathwithprocedure' ? pathcount + 1 : treeobj?.idx + 1 || pathcount + 1}</Typography>
                                <Tooltip title='Next path'>
                                    <IconButton sx={pathcount > pathdata.length - 2 ? { visibility: 'hidden' } : { visibility: 'visible' }} onClick={() => incrementfun()} ><ArrowForwardOutlined sx={iconstyle2} /></IconButton>
                                </Tooltip>
                                {/* <Typography variant="subtitle" component='span' style={{ flexGrow: 1 }}>{pathcount + 1}</Typography> */}
                                {/* <IconButton color="secondary" onClick={() => decrementfun()}><RemoveOutlined /></IconButton> */}
                                {/* <IconButton color="secondary" onClick={() => incrementfun()}><AddOutlined /></IconButton> */}

                                {!(Object.keys(treeobj).length == 0 || treeobj == {} || Agsc) && <Paper fullWidth sx={{ display: 'inline', borderRadius: '5px', position: 'absolute', right: '10px', marginTop: '10px', marginRight: '10px' }} elevation={2}>
                                    <Typography sx={{ padding: '5px', display: 'block' }}> <span style={{ ...iconstyle2, fontWeight: 'bold' }}>Estimated Cost : </span>$ {treeobj?.path?.path_cost?.toFixed(2)}</Typography>
                                    {/* <Typography  sx={{padding:'5px',display:'block'}}> <span style={{...iconstyle2,fontWeight:'bold'}}>Estimated yield : </span>{Number(treeobj.path.path_yield).toFixed(2)}</Typography> */}
                                    <Typography sx={{ padding: '5px', display: 'block' }}> <span style={{ ...iconstyle2, fontWeight: 'bold' }}>Pathway Ranking Score : </span>{treeobj?.path?.pathway_ranking_score?.toFixed(2)}</Typography>
                                    {/* {UID.paths_pro_req != undefined && Tabval != 'pathwithprocedure' && UID?.scores == 'true' && <Typography sx={{ padding: '5px', display: 'block' }}> <span style={{ ...iconstyle2, fontWeight: 'bold', display: 'flex' }}>Procedure:<ProcedureReq pathinfo={UID} pathid={treeobj.idx} /></span>
                                    </Typography>} */}
                                    {/* {
                            !UID?.ElNrequested?.includes(treeobj.idx) &&
                            <Button variant='outlined' sx={{display:'inline',color: "#323259",borderColor:"#323259", borderRadius:'5px',marginTop:'10px', marginRight:'10px' , width:'100%' }} onClick={()=>{
                            setELNPATH(treeobj)
                            setELNopen(true)
                         }}>Add to ELN</Button>} */}
                                </Paper>}


                            </div>}
                        <div id="TREE" style={containerStyles} ref={containerRef}>
                            {(MSG != '') ? <Typography sx={{ marginLeft: '30px', marginTop: '50px', color: 'red' }}>{MSG}</Typography> :
                                (Object.keys(treeobj).length == 0 || treeobj == {}) ?
                                    <LinearProgress color="secondary" />
                                    :

                                    <Tree
                                        data={treeobj.path}
                                        nodeSize={nodeSize}
                                        translate={translate}
                                        pathFunc={'step'}
                                        leafNodeClassName="node_leaf"
                                        zoomable={true}
                                        zoom={
                                            treeobj?.path?.num_steps > 0
                                                ? (Agsc ? 0.45 : 0.65) / treeobj.path.num_steps
                                                : 1
                                            }
                                        scaleExtent={{ max: 3, min: 0.15 }}
                                        depthFactor={'180'}
                                        collapsible={false}
                                        separation={{ siblings: 1.8, nonSiblings: 1.8 }}
                                        enableLegacyTransitions={true}
                                        renderCustomNodeElement={(rd3tProps) =>
                                            renderForeignObjectNode({
                                                ...rd3tProps,
                                                foreignObjectProps,
                                                referenceProps,
                                                handlereferencedialog,
                                                handlenodedialog,
                                                navigate,
                                                ColorButton,
                                                handleintermdialog,
                                                handleCheckbox,
                                                checkboxstate,
                                                setcheckboxalertdialog,
                                                handlesmilesCopysnack,
                                                UID,
                                                Agsc,
                                                setSharexpdialog,
                                                currentUser: currentUser
                                            })
                                            // : renderForeignObjectNode2({
                                            //     ...rd3tProps,
                                            //     foreignObjectProps2,
                                            //     referenceProps2,
                                            //     handlenodedialog,
                                            //     handleintermdialog,
                                            //     ColorButton,
                                            //     handlereferencedialog,
                                            //     foreignObjectProps,
                                            //     handleCheckbox,
                                            //     checkboxstate,
                                            //     setcheckboxalertdialog,
                                            //     handlesmilesCopysnack,
                                            //     UID,
                                            //     getprojects,
                                            //     setSharexpdialog,
                                            // })
                                        }
                                        orientation="vertical"
                                    />
                            }
                        </div>
                        {(intermoutput.length > 0 && Minimize == true) &&
                            <Tooltip title="Show">
                                <IconButton
                                    onClick={() => { setMinimize(false) }}
                                    style={{
                                        position: 'sticky',
                                        bottom: '200px',
                                        left: '100%',
                                        transform: 'translateX(-50%)',
                                        zIndex: 1,
                                    }}
                                >
                                    <ArrowBackIosRoundedIcon sx={{ backgroundColor: 'white', ...iconstyle2 }} />
                                </IconButton>
                            </Tooltip>}


                    </MainCard>
                </Grid>
                {
                    (intermoutput.length > 0 && Minimize == false) &&
                    <Grid item xl={4} md={6} sm={12} xs={12}>
                        <MainCard >
                            {(intermoutput.length != 0) ?


                                intermoutput.map((data) => <>

                                    <div style={{ display: 'flex', marginBottom: '20px', alignItems: 'center', alignContent: 'center', }}><Typography sx={{ marginRight: '20px' }}>Request Status: </Typography>{StatusBar(data.status)}</div>
                                    <TotalIncomeCard
                                        outputid={data.target_mol} outputdata={data} template={template} updateobject={(data) => handleupdateobject(data)} />
                                </>)
                                : 'no intermediates were requested'}
                        </MainCard>
                        <Tooltip title="Hide">
                            <IconButton
                                onClick={() => { setMinimize(true) }}
                                style={{
                                    position: 'sticky',
                                    bottom: '200px',
                                    left: '50%',
                                    transform: 'translateX(-50%)',
                                    zIndex: 1,
                                }}
                            >
                                <ArrowForwardIosRoundedIcon sx={{ backgroundColor: "white", ...iconstyle2 }} />
                            </IconButton>
                        </Tooltip>
                    </Grid>
                }
            </Grid>



            <Dialog open={referencedialog} PaperProps={{
                sx: {
                    width: '50vw',
                    height: '40vh',
                    maxWidth: '50vw',
                    maxHeight: '40vh',
                     
                },
            }} disablePortal={true} disableEscapeKeyDown={false} onClose={closeReferenceDialog}>
                <DialogTitle fullWidth={true} sx={{
                    color: "white",
                    backgroundColor: "black", ...iconstyle2, fontWeight: 'bold',
                    fontSize: '1.15rem', textAlign: 'center', paddingTop: '5px', paddingBottom: '5px', boxShadow: '0px 1px 5px 0px #f4f4f5'
                }}>
                    <Tabs value={reftab} onChange={(e, newvalue) => setreftab(newvalue)}
                                        sx={{
                    '& .MuiTab-root': { color: 'rgba(255, 255, 255, 0.7)' }, 
                    '& .MuiTab-root.Mui-selected': { color: 'white' },      
                    '& .MuiTabs-indicator': { backgroundColor: 'white' },    
                    }}
                    >
                        <Tab label='Scores' value='scores' />
                        {

                            UID?.paths_pro_available?.includes(treeobj?.idx) &&
                            <Tab label='References' value='reference' />
                        }
                        {
                            UID?.paths_pro_available?.includes(treeobj?.idx) &&
                            <Tab label='conditions' value='conditions' />
                        }
                    </Tabs>
                </DialogTitle>
                <DialogContent className='REflist' sx={{ overflowY: 'scroll', overflowX: 'hidden', width: '100%' }}>

                    <>
                        {
                            reftab == 'scores' &&
                            <div>
                                <TableContainer elevation='4' sx={{ paddingTop: '10px' }}>
                                    <Table aria-label="customized table">
                                        <TableBody>
                                            {["reaction_class",
                                                "reaction_name",
                                                "template_relev_score",
                                                "forward_scores",
                                                "scores",
                                                "fwd_feas_probs",
                                                "reaction_yield",
                                                "rebolt_score"].map((data, index) => {
                                                    return (
                                                        <StyledTableRow key={index}>
                                                            <StyledTableCell>{data}</StyledTableCell>
                                                            <StyledTableCell>
                                                                <Typography sx={{ padding: '9px' }}>{referencedata.length > 0 ? referencedata[0][data] : ''}</Typography>
                                                            </StyledTableCell>
                                                        </StyledTableRow>
                                                    )
                                                })
                                            }
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </div>
                        }
                        {referencedata?.length > 0 && reftab == 'reference' &&
                            <TableContainer className='REflist' elevation='4' sx={{ paddingTop: '10px', marginLeft: '16px' }}>
                                <Table aria-label="customized table">
                                    <TableBody>
                                        {refusid.map((data, index) => {
                                            return (
                                                <StyledTableRow key={index}>
                                                    <StyledTableCell>{index + 1}</StyledTableCell>
                                                    <StyledTableCell>
                                                        <Typography>{data}</Typography>
                                                    </StyledTableCell>
                                                    <StyledTableCell>
                                                        <ColorButton onClick={() => {
                                                            setrefdialog(true)
                                                            setX(refusid.indexOf(data))
                                                        }}>view</ColorButton>
                                                    </StyledTableCell>
                                                </StyledTableRow>
                                            )
                                        })}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        }
                        {
                            referencedata?.length > 0 && reftab == 'conditions' &&
                            <div style={{ margin: '5px' }}>
                                <Condition_Comp Data={referencedata[0]?.conditions} />
                            </div>
                        }

                    </>
                </DialogContent>
                <Divider />
                <DialogActions>
                    <Grid container display='block' spacing={2}>
                        <Grid item>
                            <ColorButton2 fullWidth={true} onClick={closeReferenceDialog} endIcon={<CloseOutlined />}>Close</ColorButton2>
                        </Grid>
                    </Grid>
                </DialogActions>
            </Dialog>



            {/*reference dialog */}
            <Dialog open={refdialog} maxWidth={'md'} disableEscapeKeyDown={false}
                    sx={{
                            zIndex: 9999,
                            pointerEvents: 'auto',
                            '& .MuiDialog-container': { pointerEvents: 'auto' },
                            '& .MuiPaper-root': { pointerEvents: 'auto' },
                        }}
            >
                <DialogTitle fullWidth={true} sx={{
                    backgroundColor: theme?.palette.secondary.light, ...iconstyle2, boxShadow: '0px 1px 5px 0px #323259', textAlign: 'center', fontWeight: 'bold',
                    fontSize: '1rem', paddingTop: '5px', paddingBottom: '5px'
                }}>
                    <IconButton color="primary" sx={X < 1 && { visibility: 'hidden' }} onClick={() => setX(X - 1)}><ArrowBackOutlined sx={iconstyle2} /></IconButton>
                    Reference no: {X + 1}
                    <IconButton color="primary" sx={X >= refusid.length - 1 && { visibility: 'hidden' }} onClick={() => setX(X + 1)}><ArrowForwardOutlined sx={iconstyle2} /></IconButton>
                </DialogTitle>
                <DialogContent sx={{ maxHeight: '400px', minHeight: '400px' }} >
                    {
                        referencedata.length > 0 &&
                        <>
                            <Typography variant="h5" component='h5' sx={{ paddingTop: '10px' }}>
                                <span style={{ fontWeight: 'bold', fontSize: '1rem', color: 'black' }}> USPTOID :</span> {refusid[X]}
                            </Typography>
                            <Accordion defaultExpanded={true}>
                                <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    aria-controls="panel1a-content"
                                    id="panel1a-header"
                                >
                                    <Typography sx={{ fontWeight: 'bold', fontSize: '1rem', color: 'black' }}>Title</Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Typography>
                                        {reftitle[X]}
                                    </Typography>
                                </AccordionDetails>
                            </Accordion>
                            <Accordion defaultExpanded={true}>
                                <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    aria-controls="panel2a-content"
                                    id="panel2a-header"
                                >
                                    <Typography sx={{ fontWeight: 'bold', fontSize: '1rem', color: 'black' }}>
                                        Procedure
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Typography sx={{ textAlign: 'justify' }}>
                                        {refprocedure[X]}
                                    </Typography>
                                </AccordionDetails>
                            </Accordion>
                            <Grid container spacing={2}>
                                <Grid item sm={6}>
                                    <Typography variant="h6" component='h6'>

                                    </Typography>
                                </Grid>
                                <Grid item sm={6} >
                                    <Typography variant="h6" component='h6'>

                                    </Typography>
                                </Grid>
                            </Grid>
                        </>
                    }
                </DialogContent>
                <Divider />
                <DialogActions>
                    <Grid container spacing={2}>
                        <Grid item sm={6} xs={6}>
                            <ColorButton2 endIcon={<CancelOutlined />} onClick={() => setrefdialog(false)}>
                                Close
                            </ColorButton2>
                        </Grid>
                        <Grid item sm={6} xs={6}>

                            <div style={{ display: 'block', textAlign: 'center' }}>
                                <Typography variant="h3" component='a' sx={iconstyle2} target="blank" href={reflink[X]}>Open Link</Typography>
                            </div>
                        </Grid>
                    </Grid>
                </DialogActions>
            </Dialog>

            {/*node dialog*/}
            <Dialog open={nodedialog} maxWidth='xl' disablePortal={true} >
                <DialogContent className="Chatscroll" sx={{ overflow: 'hidden' }}>
                    <Grid container spacing={2} sx={{ width: '700px', maxHeight: "300px", minHeight: "300px" }}>
                        <Grid item sm={6} md={6} xl={6} sx={{ width:"40%",overflowY: 'scroll', maxHeight: "300px", minHeight: "300px", display:"flex", justifyContent:"center", alignItems:"center" }}  >
                            {
                                nodedialogdata.map((data) =>
                                    <div>
                                        <ExampleCanvas structure={data.smile} />
                                    </div>
                                )
                            }
                        </Grid>
                        <Grid item sm={6} md={6} xl={6}>
                            <Tabs onChange={(event, newvalue) => { setnodeTab(newvalue) }} value={nodeTab} textColor="secondary" sx={{ marginBottom: '15px' }}>
                                <Tab label="Purchase links" sx={{ ...iconstyle2, fontWeight: 'bold' }} value="Buy" >Purchase links</Tab>
                                <Tab label="Scores and Hazards" sx={{ ...iconstyle2, fontWeight: 'bold' }} value="hazards">Scores and Hazards</Tab>
                            </Tabs>
                            {
                                nodeTab == "Buy" ? <div>

                                    {
                                        Vendorsdata.map((data) => {
                                            var Vname = data.split('/')[2]
                                            let SRC


                                            switch (Vname) {
                                                case 'mcule.com': SRC = Mculelogo;
                                                    break;
                                                case 'www.vitasmlab.biz': SRC = Vitasm;
                                                    break;
                                                case 'www.ebi.ac.uk': SRC = Chembl;
                                                    break;
                                                case 'otavachemicals.com': SRC = Otava;
                                                    break;
                                                case 'chem-space.com': SRC = Chemspace;
                                                    break;
                                                case 'shop.lifechemicals.com': SRC = Lifechemicals;
                                                    break;
                                                case 'www.chemdiv.com': SRC = Chemdiv;
                                                    break;
                                                case 'search.emolecules.com': SRC = emol;
                                                    break;
                                                case 'store.apolloscientific.co.uk': SRC = Apollo;
                                            }



                                            return (

                                                <Grid container rowSpacing={5} columnSpacing={{ xs: 1, sm: 2, md: 3 }}>
                                                    <Grid item sx={{width:"40%"}} xs={6}>
                                                        <img src={SRC} style={{ height: '15px', maxWidth: '100%' }} />
                                                    </Grid>
                                                    <Grid item xs={6}sx={{width:"40%"}}>
                                                        <Typography variant="h3" component='a' sx={{ ...iconstyle2, fontSize: '1rem' }} target="blank" href={data}>Buy Chemical</Typography>
                                                    </Grid>
                                                </Grid>
                                            )
                                        })
                                    }
                                </div>
                                    : <div style={{ margin: '10px' }}>
                                        {nodedialogdata.length > 0 &&
                                            <p><span style={{ fontWeight: 'bold' }}>SA score : </span>{isNaN(nodedialogdata[0]?.score) ? nodedialogdata[0]?.score : nodedialogdata[0]?.score?.toFixed(3)}</p>}
                                        {nodedialogdata.length > 0 && nodedialogdata.scscore &&
                                            <p><span style={{ fontWeight: 'bold' }}>SC score : </span>{isNaN(nodedialogdata[0]?.score) ? nodedialogdata[0]?.score : nodedialogdata[0]?.scscore[1]?.toFixed(3)}</p>}
                                        {nodedialogdata.length > 0 &&
                                            <TableContainer className='REflist' sx={{ maxHeight: 200, overflowY: "auto", marginBottom: '10px' }}>
                                                <Table stickyHeader >
                                                    <TableHead>
                                                        <StyledTableRow >
                                                            <StyledTableCell sx={{ ...hazardcellstyle }}>
                                                                Hazard
                                                            </StyledTableCell>
                                                            <StyledTableCell sx={{ ...hazardcellstyle }}>Message</StyledTableCell>
                                                            <StyledTableCell sx={{ ...hazardcellstyle }}>Hazard Class</StyledTableCell>
                                                        </StyledTableRow>
                                                    </TableHead>
                                                    <TableBody>
                                                        {
                                                            nodedialogdata[0]?.pubchem_hazards && Object.entries(nodedialogdata[0]?.pubchem_hazards).map(([key, value], index) => {
                                                                return (
                                                                    <StyledTableRow key={index}>
                                                                        <StyledTableCell sx={{ ...hazardcellstyle }}>{key}</StyledTableCell>
                                                                        <StyledTableCell sx={{ ...hazardcellstyle }}>{value?.message}</StyledTableCell>
                                                                        <StyledTableCell sx={{ ...hazardcellstyle }}>{value?.["Hazard Class"]}</StyledTableCell>
                                                                    </StyledTableRow>
                                                                )
                                                            })

                                                        }
                                                    </TableBody>
                                                </Table>
                                            </TableContainer>
                                        }

                                    </div>
                            }
                        </Grid>
                    </Grid>
                </DialogContent>
                <Divider />
                <DialogActions>
                    <Grid container spacing={2} sx={{ width: '500px' }}>
                        <Grid item sm={12} xs={12}>
                            <ColorButton2 endIcon={<CancelOutlined />} fullWidth={true} onClick={() => { setnodedialog(false); setVendorsdata([]) }}>
                                Close
                            </ColorButton2>
                        </Grid>
                    </Grid>
                </DialogActions>
            </Dialog>

           

            {/* // show intermediate routes dialog */}
            <Dialog open={ShowmoreRoutes}>
                <DialogTitle fullWidth={true} >
                    <Subappbar
                        icon1={<ArrowBackOutlined sx={iconstyles} />}
                        navigate1={() => navigate(-1)}
                        title="Intermediates"
                    />
                </DialogTitle>

                <DialogContent>
                    <Grid item xl={4} md={6} sm={12} xs={12}>
                        <MainCard >
                            {(intermoutput.length != 0) ?


                                intermoutput.map((data) => <>
                                    {StatusBar(data.status)}
                                    <TotalIncomeCard
                                        outputid={data.target_mol} outputdata={data} updateobject={(data) => handleupdateobject(data)} />
                                </>)
                                : 'no intermediates were requested'}
                        </MainCard>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <ColorButton2 endIcon={<CancelOutlined />} fullWidth={true} onClick={() => {

                        settreeobj(pathdata[pathcount])
                        setShowmoreRoutes(false)
                    }}>
                        Close
                    </ColorButton2>
                </DialogActions>
            </Dialog>




            {/*geneating routes requirement error*/}
            <Dialog
                open={checkboxalertdialog}
                aria-labelledby="alert-dialog-title"
                aria-describedby="alert-dialog-description"
            >
                <DialogContent>
                    <Alert severity="error">cant connect to this path, intermediates are for path </Alert>
                </DialogContent>
                <DialogActions>
                    <Button color="secondary" variant="contained" size="small" onClick={() => setcheckboxalertdialog(false)} autoFocus>
                        Ok
                    </Button>
                </DialogActions>
            </Dialog>


            {/* Download dialog */}

            <Dialog open={Dwndiag} >
                <DialogContent
                    sx={{ display: 'none' }}
                >
                    {Dwndiag && <DwnPdf treedata={treeobj} template={'retrosynthesis'} />}
                </DialogContent>
                <Divider />
                <DialogActions>
                    <Grid container spacing={2} direction="column" justifyContent="center" alignItems="center">
                        <Grid item sm={6} xs={12}>
                            <ColorButton endIcon={<Download />} onClick={() => {
                                setDwndiag(false)
                                DwnSVG()
                            }}>
                                Download SVG
                            </ColorButton>
                        </Grid>
                        <Grid item sm={6} xs={12}>
                            <ColorButton endIcon={<Download />} fullWidth={true} onClick={() => {
                                Downpdf({ treeobj: treeobj.path })
                                setDwndiag(false)
                            }}>
                                Download PDF
                            </ColorButton>
                        </Grid>
                        <Grid item sm={10} xs={12} >
                            <ColorButton endIcon={<CancelOutlined />} onClick={() => {
                                setDwndiag(false)
                            }}
                                padding={12} >
                                cancel
                            </ColorButton>
                        </Grid>
                    </Grid>
                </DialogActions>
            </Dialog>



            {/*shared experiments dialogue*/}
            {/* <Dialog
                open={ShareExpdialog}
                aria-labelledby="alert-dialog-title"
                aria-describedby="alert-dialog-description"
            >
                <DialogContent>
                <Grid>  
                <Grid item xl={6} md={6} xs={12} sm={12} marginTop='16px'>    
                      <Alert severity="info">Please Add experiment to Make changes</Alert>
                 </Grid> 
                 <Grid item xl={12} sm={12} marginTop='16px'>
                     <TextField fullWidth={true} value={Sexperimentname} id="outlined-basic" label="Experiment Name" variant="outlined" onChange={(e) => setSexperimentname(e.target.value)} />
                 </Grid>    
 
                     <Grid item xl={6} md={6} xs={12} sm={12} marginTop='16px'>
                         <SelectProjectWrapper
                                         label={'select project'}
                                         handlefield={(name,value) => {
                                           setproject(value)
                                         }}
                                       />
                      </Grid>
                      </Grid>

             </DialogContent>
                <DialogActions>
                    <Button color="secondary" variant="contained" fullWidth={true} size="small" onClick={() =>{setSharexpdialog(false)
                    SubmitExperiment()
                    }} autoFocus>
                    Submit
                    </Button>
                </DialogActions>
                <DialogActions>
                    <Button color="secondary" variant="contained" fullWidth={true} size="small" onClick={() =>{setSharexpdialog(false)
                    setSexperimentname('')
                    setAge('')}} autoFocus>
                    cancel
                    </Button>
                </DialogActions>
            </Dialog> */}




            {/* <Dialog open={ElNopen} onClose={()=>{
            setELNopen(false)
        }} maxWidth={'xl'}>
          <DialogContent>
            <DialogContentText sx={{marginBottom:'20px',color:'#323259',fontWeight:'bold'}}>
              Create New ELN 
            </DialogContentText>
            <Grid container spacing={2} component={Paper}>
              <Grid item sm={12} xs={12} md={12} xl={6} sx={{ width: '200px' }}>
                <TextField
                  autoFocus
                  margin="dense"
                  label="ELN Project Name"
                  type="text"
                  fullWidth
                  variant="outlined"
                  name="projectname"
                  onChange={(e)=>{
                    if(showErrMsg){
                        setshowerrMsg(false);
                        setErrorMsg('')
                    }
                    setELNdata((prevData) => ({
                       ...prevData,
                    name: e.target.value}));}}
                  value={ELNdata.name}
                />

              </Grid>
              <Grid item sm={12} xs={12} md={12} xl={6} sx={{ width: '200px' }}>
                <TextField
                  margin="dense"
                  label="Description"
                  type="text"
                  fullWidth
                  variant="outlined"
                  name="projectdesc"
                  onChange={(e)=>{
                    if(showErrMsg){
                        setshowerrMsg(false);
                        setErrorMsg('')
                    }
                    setELNdata((prevData) => ({
                       ...prevData,
                    description: e.target.value}));}}
                  value={ELNdata.description}
                />

                {showErrMsg && <p>{errorMsg}</p>}
              </Grid>

            </Grid>
          </DialogContent>
          <Divider />
          <DialogActions>
            <Grid container spacing={2}>
              <Grid item sm={6} xs={12} md={6} xl={6}>
                <ColorButton2 endIcon={<CancelOutlined />} onClick={()=>{
                    setELNdata({name:'',description:''})
                    setELNPATH({})
                    setELNdata(false)
                }} fullWidth={true} variant='outlined'>Close</ColorButton2>
              </Grid>
              <Grid item sm={6} xs={12} md={6} xl={6}>
                <ColorButton endIcon={<SubdirectoryArrowRightOutlinedIcon />} onClick={()=>{ElNfunction()}} fullWidth={true} variant='outlined'>Create</ColorButton>
              </Grid>
            </Grid>
          </DialogActions>
        </Dialog> */}


            {/*save success snack bars */}
            {/* <Snackbar
                open={savesnackstate}
                autoHideDuration={6000}
                message={'successfully saved experiment'}
                action={
                    <>
                        <IconButton
                            aria-label="close"
                            color="inherit"
                            sx={{ p: 0.5 }}
                            onClick={() => setsavesnackstate(false)}
                        >
                            <CloseOutlined />
                        </IconButton>
                    </>
                }
            /> */}
            <Stack spacing={2} sx={{ width: '100%' }}>
                <Snackbar open={savesnackstate} autoHideDuration={2000} onClose={() => { setsavesnackstate(false) }} anchorOrigin={{ horizontal: 'right', vertical: 'top' }}>
                    <Alert onClose={() => setsavesnackstate(false)} severity="success" sx={{ width: '100%', backgroundColor: 'green', color: 'white' }}>
                        Copy of the tree was successfully saved
                    </Alert>
                </Snackbar>
            </Stack>
            <Stack spacing={2} sx={{ width: '100%' }}>
                <Snackbar open={smilesCopysnack} autoHideDuration={2000} onClose={() => { setsmilesCopysnack(false) }} anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}>
                    <Alert onClose={() => setsmilesCopysnack(false)} severity="success" sx={{ width: '100%', backgroundColor: 'green', color: 'white' }}>
                        SMILES copied to clipboard
                    </Alert>
                </Snackbar>
            </Stack>
            <Stack spacing={2} sx={{ width: '100%' }}>
                <Snackbar open={Sexperimentsnack} autoHideDuration={2000} onClose={() => { setSexperimentsnack(false) }} anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}>
                    <Alert onClose={() => setsavesnackstate(false)} severity="success" sx={{ width: '100%', backgroundColor: 'green', color: 'white' }}>
                        Experiment was successfully added
                    </Alert>
                </Snackbar>
            </Stack>
            <Stack spacing={2} sx={{ width: '100%' }}>
                <Snackbar open={Elsnack} autoHideDuration={2000} onClose={() => { setSexperimentsnack(false) }} anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}>
                    <Alert onClose={() => setsavesnackstate(false)} severity="success" sx={{ width: '100%', backgroundColor: 'green', color: 'white' }}>
                        ELN project successfully added
                    </Alert>
                </Snackbar>
            </Stack>

        </>
    );
}

