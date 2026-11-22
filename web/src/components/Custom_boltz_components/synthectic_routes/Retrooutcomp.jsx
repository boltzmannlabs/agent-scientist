

import { Box, Tab, Tabs, Typography } from '@mui/material';
import features from 'components/search-data/features.json';
import { nodejsapi } from "config";
import { useEffect, useState } from "react";
import { DocfetchMultiAPI, fetchFileContentJSON } from 'services/servfunctions';
import { useWebSocket } from 'socketup';
import { useToken } from "tokenfetch";
import D3tree from "./D3tree";
import RetrosynthesisOutput from "./RetrosynthesisOutput";
import CollaboratorComp from 'ui-component/subappbar/collaboratorcomponent';
import ExperimentLoader from "components/loaders/ExperimentLoader";
import OutputError from "components/OutputError";




const Retrooutcomp = ({ eid, template, Agsc, pid, uid }) => {

  const [UID, setUID] = useState({})
  const [MSG, setMSG] = useState('')
  const [DataP, setDataP] = useState([])
  const [Datast, setDatast] = useState([])
  const [allP, setallP] = useState(false)
  const [Tabval, setTabval] = useState('pathways')
  const [currentpath, setcurrentPath] = useState(0)
  const [Loadoff, setLoadoff] = useState(false)
  const [Cluster, setCluster] = useState(false)
  const [clusterNUM, setclusterNUM] = useState([])
  const [currentCluster, setCurrentcluster] = useState(null)
  const [clusterArr, setClusterArr] = useState([])
  const [currentstep, setCurrentstep] = useState(0)
  const [Procedurepath, setProcedurepath] = useState([])
  const [showPathswithProcedure, setshowPathswithProcedure] = useState(false)
  let selectedFeature = features.find(feature => feature.id === 75);

  const sockets = useWebSocket()




  const [userRole, setUserRole] = useState('')
  const [expName, setExpName] = useState('')

  const [errorStatus, setErrorStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const clustering = async (dats, uid) => {
    let clustered = {}
    let startingmaterials = dats
    if (uid?.clusters?.length > 0) {

      Promise.all(
        Object.entries(startingmaterials).map((data) => {
          const val = Number(data[0])

          const value = uid.clusters[val]

          if (!clustered[value]) {
            clustered[value] = [];
          }
          clustered[value].push({ ...data })

        })
      )
      setClusterArr(clustered)
      setclusterNUM(Object.keys(clustered))
    }
  }








  const fetchJsonFile = async ({ path, uid, status }) => {

    const collect = [];

    await Promise.all(
      path
        .filter((data) => data != null)
        .map(async (data) => {
          setMSG('');
          try {
            const finaljsonData = await fetchFileContentJSON(nodejsapi, data);
            if (finaljsonData) {
              const countarr = Object.keys(finaljsonData).map((key) => finaljsonData[key]);


              collect.push(...countarr);


              setDataP((prev) => {
                // Create a map of previous items by idx
                const map = new Map(prev.map(item => [item.idx, item]));

                countarr.forEach(item => {
                  map.set(item.idx, item);
                });

                // Return sorted array
                return Array.from(map.values()).sort((a, b) => a.idx - b.idx);
              });
            }
          } catch (err) {
            console.log("Error fetching JSON for", data, err);
          }
        })
    );

    // Sort only once at the end
    collect.sort((a, b) => a.idx - b.idx);

    if (status === '100% completed') {
      clustering(collect, uid);
    }
  };


  const viewclusterpaths = async (pathnum, clusternum) => {
    const CPS = []

    Promise.all(clusterArr[clusternum].map((dat) => {
      CPS.push(dat[1])
    }))
    setDataP(CPS)
    setCurrentcluster(clusternum)
    setcurrentPath(pathnum)
    setallP(false)
  }

  const Currentpathfun = (data) => {
    setcurrentPath(data)
  }



  const updateprocedurepaths = async () => {
    try {
      if (UID != {}) {
        if (UID?.procedures_paths) {
          const collect = []
          const finaljsonData = await fetchFileContentJSON(nodejsapi, UID?.procedures_paths).catch((err) => console.log(err));

          if (finaljsonData) {
            const countarr = Object?.keys(finaljsonData)?.map(key => finaljsonData[key]);
            collect.push(...countarr);
            collect.sort(((a, b) => a.idx - b.idx))
            setProcedurepath(collect)
          }
        }
        else {
          await DocfetchMultiAPI({ apisubstring: 'retrosynthesis', Docid: eid }).then(async (dat) => {
            let data = dat.data
            if (data.procedures_paths) {
              const collect = []
              const finaljsonData = await fetchFileContentJSON(nodejsapi, UID?.procedures_paths).catch((err) => console.log(err));
              if (finaljsonData) {
                const countarr = Object?.keys(finaljsonData)?.map(key => finaljsonData[key]);
                collect.push(...countarr);
                collect.sort(((a, b) => a.idx - b.idx))
                setProcedurepath(collect)
              }
            }
          })
        }

      }
    } catch (error) {
      console.log(error);

      setErrorStatus(
        error?.response?.status
      );
    }
  }

  const getref = async () => {
    try {
      setLoading(true);
      setDataP([]);

      const dat = await DocfetchMultiAPI({
        apisubstring: 'retrosynthesis',
        Docid: eid
      });

      let data = dat.data;

      if (
        data.status === "100% completed" &&
        data.paths.length === 0
      ) {
        setMSG(
          'No paths found for the molecule or molecule already in building blocks'
        );
      } else {

        setUID({ ...data });
        setUserRole(dat?.userRole);
        setExpName(dat?.data?.name);
        if (data.scores === 'true') {
          if (data.paths_) {
            fetchJsonFile({
              path: data.paths_,
              uid: data,
              status: data.status
            });
          }
        } else {
          if (data.paths) {
            fetchJsonFile({
              path: data.paths,
              uid: data,
              status: data.status
            });
          }
        }
      }

    } catch (error) {
      console.log(error);

      setErrorStatus(
        error?.response?.status
      );
    } finally {
      setLoading(false);
    }
  };



  const viewall = () => {
    setallP(true)
    setLoadoff(true)
    setTimeout(() => {
      setLoadoff(false)
    }, 200)
  }

  const clusterview = () => {
    setLoadoff(true)
    if (Cluster == true) {
      setDataP(Datast)
    }
    setCluster(!Cluster)
    setTimeout(() => {
      setLoadoff(false)
    }, 200)
  }

  const PV = (pathnum) => {
    setcurrentPath(pathnum)
    setTabval('pathways')
  }


  useEffect((stepno) => {
    setCurrentstep()
  }, [])

  useEffect(() => {
    updateprocedurepaths()
  }, [UID])






  useEffect(() => {
    getref()
  }, [])


  useEffect(() => {
    if (!sockets) {
      return;
    }
    sockets.onAny((event, data) => {
      //  console.log(`📡 Event received: ${event}`);

    });

    const handleRetrochange = (data) => {
      if (data?.["docid"] === eid) {

        const updatedFields = data?.["description"]?.["updatedFields"];
        if (updatedFields) {
          const keys = Object.keys(updatedFields);

          if (keys.includes("scores")) {
            getref();
          }
          else {
            let modkey = keys[0].split('.')[0]
            if (modkey = "paths_pro_available") {
              updateprocedurepaths();
            }
            if (modkey = "paths") {
              getref()
            }

          }
        }
      }
    }

    sockets.on("retrosynthesisChanged", handleRetrochange);

    return () => {
      //  console.log("🚨 Removing socket listeners...");
      sockets.off("retrosynthesisChanged", handleRetrochange);
    };
  }, [sockets]);


  if (loading) {
    return <ExperimentLoader />;
  }

  if (errorStatus) {
    return <OutputError status={errorStatus} />;
  }


  return (
    <>
      <Box sx={{ p: 1, mb: 1 }}>
        <Typography
          variant="h4"
          component="h4"
          sx={{ mb: 0.3 }}
        >
          {selectedFeature ? selectedFeature.name : 'Retrosynthesis'}
        </Typography>

        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            px: 1,
            py: 0.3,
            borderRadius: "14px",
            border: "1.5px solid",
            borderColor: "primary.main",
            position: "relative",
            overflow: "hidden",
            mb: 1.5,
          }}
        >
          <Typography
            sx={{
              fontSize: "12px",
              fontWeight: 700,
              letterSpacing: "0.6px",
              color: "primary.main",
              lineHeight: 1.5,
              position: "relative",
              zIndex: 1,
            }}
          >
            {expName}
          </Typography>
        </Box>

        <Typography
          variant="body1"
          component="p"
          sx={{ mt: 0 }}
        >
          {selectedFeature ? selectedFeature.description : ''}
        </Typography>
      </Box>

      <>
        <tab>
          <Tabs value={Tabval} onChange={(event, newvalue) => {
            setTabval(newvalue)
          }} aria-label="basic tabs example" variant="fullWidth">
            <Tab label="All Paths" value="allpaths" />
            <Tab label="Pathways" value="pathways" />
          </Tabs>
        </tab>

        {
          Tabval != 'allpaths' ? <D3tree Data={DataP} userRole={userRole} Uid={UID} cpath={currentpath} viewall={viewall} Msg={MSG} cluster={Cluster} clusterNUM={clusterNUM} currentCluster={currentCluster} Procedurepath={Procedurepath} viewclusterpaths={viewclusterpaths} Agsc={Agsc} eid={eid} template={template} pid={UID?.project_id} Currentpathfun={Currentpathfun} Tabval={Tabval} />
            :
            <RetrosynthesisOutput Data={DataP} Uid={UID} userRole={userRole} PV={PV} clusterview={clusterview} cluster={Cluster} clustdata={clusterArr} viewclusterpaths={viewclusterpaths} load={Loadoff} />

        }
      </>
    </>
  )
}
export default Retrooutcomp