import React, { useEffect, useRef } from 'react';
import { Viewer } from '../../../node_modules/molstar/build/viewer/molstar';
import '../../../node_modules/molstar/build/viewer/molstar.css';

const MolstarComp = ({ storagelink,ext }) => {
    const viewerRef = useRef(null);

    useEffect(() => {
        console.log('stintest',storagelink)
       
        let viewer;

        const initViewer = async () => {
            if (!storagelink) return; 

            try {
                viewer = await Viewer.create('app', {
                    layoutIsExpanded: false,
                    layoutShowControls: false,
                    layoutShowRemoteState: false,
                    layoutShowSequence: true,
                    layoutShowLog: false,
                    layoutShowLeftPanel: true,
                    viewportShowExpand: true,
                    viewportShowSelectionMode: false,
                    viewportShowAnimation: false,
                    pdbProvider: 'rcsb',
                    emdbProvider: 'rcsb',
                });
            if(ext === 'sdf'){
                await viewer.loadStructureFromData(storagelink, 'sdf');
            } else if(ext === 'pdb'){
                await viewer.loadStructureFromData(storagelink, 'pdb');
            }
            else if(ext === 'cif'){
                await viewer.loadStructureFromData(storagelink, 'cif');
            }
            } catch (err) {
                console.error('Error initializing Viewer:', err);
            }
        };

        const cleanupViewer = () => {
            if (viewer) {
                viewer.dispose();
                viewer = null;
            }
        };

        initViewer();

        return () => {
            cleanupViewer();
        };
    }, [storagelink,storagelink2]);

    return <div id="app" className='mol-star'></div>;
};

export default MolstarComp;
