import { useEffect, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { createPluginUI } from 'molstar/lib/mol-plugin-ui';
import { DefaultPluginUISpec } from 'molstar/lib/mol-plugin-ui/spec';
import type { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { PluginConfig } from 'molstar/lib/mol-plugin/config';
import { PluginCommands } from 'molstar/lib/mol-plugin/commands';
import { Color } from 'molstar/lib/mol-util/color';
import 'molstar/build/viewer/molstar.css';
import { api } from '@/lib/api';
import { errorMessage } from '@/lib/api-error';
import { decodeStructureFile, MAX_STRUCTURE_BYTES, structureFormat, validateStructureSize, type StructureSource } from '@/lib/structure-source';

export default function StructureViewport({ source }: { source: StructureSource }) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState('Reading structure…');
  const [error, setError] = useState('');

  useEffect(() => {
    const target = container.current;
    if (!target) return;
    let cancelled = false;
    const abort = new AbortController();
    let plugin: PluginUIContext | undefined;
    let root: Root | undefined;
    let resize: ResizeObserver | undefined;
    let compact = target.clientWidth < 640;
    const dispose = () => {
      resize?.disconnect();
      const oldRoot = root; const oldPlugin = plugin;
      root = undefined; plugin = undefined;
      queueMicrotask(() => { oldRoot?.unmount(); oldPlugin?.dispose(); });
    };
    async function load() {
      try {
        const format = structureFormat(source.name);
        if (!format) throw new Error('Choose a .pdb, .cif, or .mmcif structure file.');
        let text: string;
        if (source.file) {
          validateStructureSize(source.file.size);
          text = await source.file.text();
        } else if (source.path) {
          const file = await api.readFile(source.path, abort.signal,
            source.profile ? { profile: source.profile, sessionId: source.sessionId } : undefined, MAX_STRUCTURE_BYTES);
          text = decodeStructureFile(file.data_url, file.size);
        } else throw new Error('No structure file was selected.');
        if (cancelled) return;
        setStatus('Building 3D structure…');
        const spec = DefaultPluginUISpec();
        plugin = await createPluginUI({
          target: target!,
          render: (element, elementTarget) => { root = createRoot(elementTarget); root.render(element); },
          spec: {
            ...spec,
            actions: [],
            layout: { initial: { isExpanded: false, showControls: !compact, controlsDisplay: 'reactive' } },
            components: { controls: { left: 'none', bottom: 'none' }, remoteState: 'none', disableDragOverlay: true },
            canvas3d: { renderer: { backgroundColor: Color(0x10151b) } },
            config: [
              [PluginConfig.VolumeStreaming.Enabled, false],
              [PluginConfig.Viewport.ShowExpand, false],
              [PluginConfig.Viewport.ShowToggleFullscreen, false],
            ],
          },
        });
        if (cancelled) { dispose(); return; }
        if (!plugin.canvas3d) throw new Error('3D rendering is unavailable. Enable browser hardware acceleration/WebGL, or use another browser.');
        const data = await plugin.builders.data.rawData({ data: text, label: source.name });
        const trajectory = await plugin.builders.structure.parseTrajectory(data, format);
        if (!trajectory.obj?.data.frameCount) throw new Error('This file contains no readable molecular structures.');
        await plugin.builders.structure.hierarchy.applyPreset(trajectory, 'default');
        if (cancelled) { dispose(); return; }
        const structures = plugin.managers.structure.hierarchy.current.structures;
        if (!structures.some(item => (item.cell.obj?.data.elementCount || 0) > 0)) throw new Error('No atoms were found in this structure.');
        resize = new ResizeObserver(() => {
          const nextCompact = target!.clientWidth < 640;
          if (nextCompact !== compact) {
            compact = nextCompact;
            if (plugin) void PluginCommands.Layout.Update(plugin, { state: { showControls: !compact } });
          }
          plugin?.canvas3d?.requestResize();
        });
        resize.observe(target!);
        plugin.canvas3d.requestResize();
        setStatus('');
      } catch (failure) {
        dispose();
        if (!cancelled) { setError(errorMessage(failure)); setStatus(''); }
      }
    }
    void load();
    return () => { cancelled = true; abort.abort(); dispose(); };
  }, [source]);

  return <div className="structure-stage">
    <div ref={container} className="structure-viewport" aria-label="Interactive molecular structure" />
    {status && <p className="structure-status" role="status">{status}</p>}
    {error && <p className="structure-status structure-error" role="alert">Could not display structure: {error}</p>}
  </div>;
}
