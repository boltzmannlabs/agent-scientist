import { ArrowBackOutlined, ArrowForwardOutlined, EditOutlined } from '@mui/icons-material';
import { AppBar, Toolbar, Tooltip, Typography } from '@mui/material';
import { textAlign } from '@mui/system';
import { BarChart, GridView, TableView } from '@mui/icons-material';
import { Box, Card, Grid, Tab, Tabs, ToggleButton, ToggleButtonGroup, Snackbar, Select, MenuItem, TextField, Button, Dialog, DialogActions, DialogContent, DialogTitle, } from '@mui/material';
import { Alert, IconButton, Menu, Popover } from '@mui/material';
import React, { useState, useEffect } from 'react';
import { Delete, Edit } from '@mui/icons-material';
import Groups2Icon from '@mui/icons-material/Groups2';


const Subappbar = ({
    title,
    navigate1,
    navigate2,
    navigate3,
    sxterm,
    icon1,
    icon2,
    crexpicon,
    editcopy,
    tooltip1,
    searchbar,
    Switch,
    collection,
    collabs,
    userRole,
    id,
    project
}) => {




    const [value, setValue] = useState(0);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };



    const appbarstyles = {
        backgroundColor: '#fff',
        color: '#323259',
        marginBottom: '10px',
        ...sxterm
    }
    const toolbarstyles = {
        display: 'flex',
        textAlign: 'left'
    }
    const toolbartitlestyles = {

        color: '#323259',
        flexGrow: 1,
        fontWeight: 500,
        fontSize: '.9375rem',
        lineHeight: '1.5rem',
        display: 'flex'
    }










    return (
        <>
            <AppBar position='static' sx={appbarstyles} elevation={0}>
                <Toolbar variant='dense' sx={toolbarstyles}>
                    <IconButton onClick={navigate1} sx={{ color: "#323259" }}>
                        {icon1}
                    </IconButton>
                    <IconButton onClick={navigate2} sx={{ color: "#323259" }}>
                        {icon2}
                    </IconButton>
                    <Typography variant='h3' component='h3' sx={toolbartitlestyles}>{title}</Typography>

                   
                    {
                        crexpicon &&
                        <Tooltip title={tooltip1}>

                            <Button onClick={navigate3} variant='outlined' sx={{ color: "#323259", borderColor: "#323259" }} >{crexpicon}</Button>

                        </Tooltip>}
                   
                    
                    
                </Toolbar>
            </AppBar>
        </>
    )

}

export default Subappbar;