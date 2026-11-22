import styled from "@emotion/styled";
import { Button } from "@mui/material";
import { purple } from "@mui/material/colors";
import MoleculeStructure from "./MoleculeStructure";


function ExampleCanvas({ structure }) {
  const caffeine = "O=C(CN1N=NC2=CC=CC=C12)N(CC1C=CSC=1)C1=CC=C(Cl)C=C1";
  const aspirin = "[C:2]-[CH2;D2;+0:1]-[c;H0;D3;+0:4](:[c:3]):[c:5]>>Cl-[C;H0;D3;+0:1](=O)-[C:2].[c:3]:[cH;D2;+0:4]:[c:5]";

  return (
    <div className="container" style={{display:'flex',justifyContent:'space-evenly'}}>
      <MoleculeStructure
        structure={structure}
        width={180}
        height={140}
        svgMode
      />
    </div>
  );
}

export default ExampleCanvas;
