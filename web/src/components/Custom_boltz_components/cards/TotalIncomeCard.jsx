
// material-ui
import { Accordion, AccordionDetails, AccordionSummary, Button, Card, Grid, LinearProgress } from '@mui/material';
import { useTheme } from '@mui/styles';
import { Box } from '@mui/system';
import { nodejsapi } from "config";
import { useEffect, useState } from 'react';
import { fetchFileContentJSON } from 'services/servfunctions';
import ExampleCanvas from '../../Custom_boltz_components/synthectic_routes/RDkit/ExampleCanvas';
import SubCard from './SubCard';




// ==============================|| SKELETON - TOTAL INCOME DARK/LIGHT CARD ||============================== //









const TotalIncomeCard = ({
    outputid,
    outputdata,
    updateobject,
    template
}) => {


    const [paths, setpaths] = useState({})
    const [expand,setexpand] = useState(false)




    const theme = useTheme()
    
    
    const customestyles = {
        borderRadius: '0px',
        borderTop: "3px solid",
        borderColor: theme?.palette?.secondary?.dark,
        padding: '2px'
    }
    const iconstyle2 = {
        color: "#323259"
    }



    
    const Intermediatejson = async ({path}) => {
    
            
       
        const interjson = await fetchFileContentJSON(nodejsapi, path);
        setpaths({...interjson})
      }
      
      useEffect(()=>{
        if(outputdata.status=='completed'||outputdata.status=="100% completed"){
        Intermediatejson({path:outputdata.outputFilePath})}
      },[outputdata.status] )


return(
    <Card sx={customestyles}>
       {/* {(template == 'retrosynthesis') ? */}
        <Accordion expanded='true'>
            <AccordionSummary
                aria-controls="panel1a-content"
                id="panel1a-header" sx={{justifyContent: 'space-between'}}>
                <ExampleCanvas  structure={outputid} />
            </AccordionSummary>
           
            <AccordionDetails>
            {expand && 
                (paths=={}) ? <LinearProgress color="secondary" />
                    : Object.entries(paths).map((entry) =>
                        <SubCard title={entry[0]} sx={{ padding: '0px' }}>
                           
                            <Grid container spacing={2}>
                                {
                                    entry[1].path.reactants.map((data) => <>
                                        <Grid item xl={6} md={6} sm={12} xs={12}>
                                            <Card elevation={2} 
                                            sx={{border:'solid', borderWidth:'1.5px', borderColor:`${entry[1].path.reactant_colors[ entry[1].path.reactants.indexOf(data)]}`}}
                                            >
                                                <ExampleCanvas 
                                                    structure={data} />
                                            </Card>
                                        </Grid>
                                    </>)
                                }
                            </Grid>
                            <Box sx={{display:'flex',mt:2}}>
                                {/* <Typography variant='subtitle1' sx={{flexGrow:1}} color='text.secondary'>Click add to preview</Typography> */}
                                <Button variant='outlined' sx={iconstyle2} onClick={()=>updateobject({data:entry[1].path,parid:outputdata.parentnodeid,pathid:outputdata.pathid})}>Preview</Button>

                            </Box>
                        </SubCard>
                    )
                }
            </AccordionDetails>
            </Accordion>
        {/* </Accordion>  
        :
        <Accordion expanded='true'>
            <AccordionSummary
                aria-controls="panel1a-content"
                id="panel1a-header"
            >
                <ExampleCanvas  structure={outputid} />
            </AccordionSummary>
            <AccordionDetails>
                { outputdata.status === 'completed' &&
                    Object.entries(outputdata.output).map((entry) =>
                        <SubCard title={entry[0]} sx={{ padding: '0px' }}>
                           
                            <Grid container spacing={2}>
                                {
                                    entry[1].path.reacts.map((data) => <>
                                        <Grid item xl={6} md={6} sm={12} xs={12}>
                                            <Card elevation={2}>
                                                <ExampleCanvas
                                                    structure={data} />
                                              
                                            </Card>
                                        </Grid>
                                    </>)
                                }
                            </Grid>
                            <Box sx={{display:'flex',mt:2}}>
                                <Typography variant='subtitle1' sx={{flexGrow:1}} color='text.secondary'>Click add to preview</Typography>
                            <Button variant='outlined' color='secondary' onClick={()=>updateobject({data:entry[1].path,parid:outputdata.parentnodeid,pathid:outputdata.pathid})}>Add</Button>

                            </Box>
                        </SubCard>
                    )
                } 
            </AccordionDetails>
        </Accordion> */}
       {/* } */}
    </Card>
);
}
export default TotalIncomeCard;