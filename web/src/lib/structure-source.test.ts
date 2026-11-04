import { describe, expect, it } from 'vitest';
import { decodeStructureFile, MAX_STRUCTURE_BYTES, structureFormat, structureSourceFromLink, validateStructureSize } from './structure-source';

describe('structure source boundaries', () => {
  it('recognizes explicit structure files without treating external or executable links as files', () => {
    const origin = 'https://sci.example.test';
    for (const href of ['/project/model.PDB', 'file:///project/model.PDB', 'sandbox:/project/model.PDB', `${origin}/api/files/download?path=%2Fproject%2Fmodel.PDB`]) {
      expect(structureSourceFromLink(href, origin)).toEqual({ name: 'model.PDB', path: '/project/model.PDB' });
    }
    for (const href of ['https://elsewhere.example/model.pdb', 'javascript:/model.pdb', '//other/model.pdb', 'file://other/model.pdb', 'relative.pdb', '/project/script.js', '/broken%xx.pdb', '/project/a\0.pdb']) {
      expect(structureSourceFromLink(href, origin)).toBeNull();
    }
    expect(structureSourceFromLink('file:///C:/project/model.cif')?.path).toBe('C:/project/model.cif');
    expect(structureFormat('model.mmcif')).toBe('mmcif');
  });

  it('bounds and decodes file contents rather than executing data URLs', () => {
    const text = 'HEADER    fixture\nEND\n';
    expect(decodeStructureFile(`data:chemical/x-pdb;base64,${btoa(text)}`, text.length)).toBe(text);
    expect(() => decodeStructureFile('data:text/html,<script>bad</script>', 1)).toThrow('invalid');
    expect(() => validateStructureSize(0)).toThrow('empty');
    expect(() => validateStructureSize(MAX_STRUCTURE_BYTES + 1)).toThrow('20 MiB');
  });
});
