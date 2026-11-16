import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useProfileScope } from "@/contexts/useProfileScope";
import { H2 } from "@sci/ui/ui/components/typography/h2";
import { Card, CardContent } from "@sci/ui/ui/components/card";
import { Badge } from "@sci/ui/ui/components/badge";
import { Button } from "@sci/ui/ui/components/button";
import { Input } from "@sci/ui/ui/components/input";
import { Label } from "@sci/ui/ui/components/label";
import { Checkbox } from "@sci/ui/ui/components/checkbox";
import { Toast } from "@sci/ui/ui/components/toast";
import { useToast } from "@sci/ui/hooks/use-toast";
import { api, type NativeScienceProfileOptions, type NativeScienceServiceOption } from "@/lib/api";
import { errorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";

const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const STEPS = ["Project", "Science skills", "Tools", "Sources", "Review"] as const;
type Step = (typeof STEPS)[number];
type SourceAccess = "reference" | "read-local" | "model";
interface ProjectSource { location: string; access: SourceAccess }
interface ServiceDraft {
  selected: boolean;
  discoveryToken: string;
  discoveredTools: Array<{ name: string; description: string }>;
  selectedTools: string[];
  approveScope: boolean;
  discovering: boolean;
}
const emptyServiceDraft: ServiceDraft = {
  selected: false, discoveryToken: "", discoveredTools: [], selectedTools: [],
  approveScope: false, discovering: false,
};

export default function ProfileBuilderPage() {
  const navigate = useNavigate();
  const { setProfile } = useProfileScope();
  const { toast, showToast } = useToast();
  const [step, setStep] = useState<Step>("Project");
  const [options, setOptions] = useState<NativeScienceProfileOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [name, setName] = useState("");
  const [skillFilter, setSkillFilter] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [serviceFilter, setServiceFilter] = useState("");
  const [serviceDrafts, setServiceDrafts] = useState<Record<string, ServiceDraft>>({});
  const [pendingDiscovery, setPendingDiscovery] = useState<NativeScienceServiceOption | null>(null);
  const [sources, setSources] = useState<ProjectSource[]>([]);
  const [sourceLocation, setSourceLocation] = useState("");
  const [sourceAccess, setSourceAccess] = useState<SourceAccess>("reference");
  const [sourceKind, setSourceKind] = useState<"path" | "url">("path");
  const [boltzmannKey, setBoltzmannKey] = useState("");
  const [approveBoltzmannValidation, setApproveBoltzmannValidation] = useState(false);
  const [approveImageDownload, setApproveImageDownload] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{ name: string; path: string } | null>(null);

  useEffect(() => {
    let live = true;
    api.getNativeScienceProfileOptions().then(result => {
      if (!live) return;
      setOptions(result);
      setServiceDrafts(Object.fromEntries(result.services.map(service => [service.key, { ...emptyServiceDraft }])));
    }).catch(error => {
      if (live) setLoadError(errorMessage(error));
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  const validName = PROFILE_NAME_RE.test(name.trim()) && !["main", "default"].includes(name.trim());
  const filteredSkills = useMemo(() => {
    const query = skillFilter.trim().toLowerCase();
    return (options?.skills || []).filter(item => !query || `${item.name} ${item.description}`.toLowerCase().includes(query));
  }, [options, skillFilter]);
  const filteredServices = useMemo(() => {
    const query = serviceFilter.trim().toLowerCase();
    return (options?.services || []).filter(item => !query || `${item.name} ${item.description} ${item.destination || ""}`.toLowerCase().includes(query));
  }, [options, serviceFilter]);
  const selectedServices = useMemo(() => (options?.services || []).filter(service => serviceDrafts[service.key]?.selected), [options, serviceDrafts]);
  const selectedMcp = selectedServices.filter(service => service.kind === "mcp");
  const selectedPlugins = selectedServices.filter(service => service.kind === "plugin");
  const boltzmann = selectedPlugins.find(service => service.name === "boltzmann");
  const readyToSave = selectedMcp.every(service => {
    const draft = serviceDrafts[service.key];
    return Boolean(draft?.discoveryToken && draft.selectedTools.length);
  }) && selectedPlugins.every(service => serviceDrafts[service.key]?.approveScope) &&
    (!boltzmann || Boolean(boltzmannKey.trim() || boltzmann.credential_ready) && approveBoltzmannValidation);
  const incompleteServices = selectedServices.flatMap(service => {
    const draft = serviceDrafts[service.key];
    if (service.kind === "mcp" && !draft?.discoveryToken) return [`${service.name}: connect and discover its tools.`];
    if (service.kind === "mcp" && !draft?.selectedTools.length) return [`${service.name}: select at least one discovered tool.`];
    if (service.kind === "plugin" && !draft?.approveScope) return [`${service.name}: approve its complete plugin permission scope.`];
    return [];
  });
  if (boltzmann && !(boltzmannKey.trim() || boltzmann.credential_ready)) {
    incompleteServices.push("Boltzmann: provide an API key.");
  }
  if (boltzmann && !approveBoltzmannValidation) {
    incompleteServices.push("Boltzmann: approve read-only API-key validation.");
  }

  function updateService(key: string, update: Partial<ServiceDraft>) {
    setServiceDrafts(previous => ({ ...previous, [key]: { ...emptyServiceDraft, ...previous[key], ...update } }));
  }
  function toggleSkill(skill: string) {
    setSelectedSkills(previous => previous.includes(skill) ? previous.filter(item => item !== skill) : [...previous, skill]);
  }
  function toggleService(service: NativeScienceServiceOption, checked: boolean) {
    if (checked && !service.ready && service.name !== "boltzmann") return;
    updateService(service.key, { selected: checked });
  }
  function toggleTool(service: NativeScienceServiceOption, tool: string) {
    const selected = serviceDrafts[service.key]?.selectedTools || [];
    updateService(service.key, { selectedTools: selected.includes(tool) ? selected.filter(item => item !== tool) : [...selected, tool] });
  }
  function addSource() {
    const location = sourceLocation.trim();
    if (!location) return;
    if (sourceKind === "url" && !/^https:\/\//i.test(location)) {
      showToast("Reference URLs must use HTTPS.", "error");
      return;
    }
    if (sources.some(source => source.location === location)) {
      showToast("That source is already listed.", "error");
      return;
    }
    setSources(previous => [...previous, { location, access: sourceAccess }]);
    setSourceLocation("");
  }
  async function discover(service: NativeScienceServiceOption) {
    updateService(service.key, { discovering: true, discoveryToken: "", discoveredTools: [], selectedTools: [] });
    try {
      const result = await api.discoverNativeScienceMcp({
        name: service.name,
        approve_network: true,
        approve_local_execution: service.transport === "local",
      });
      updateService(service.key, { discoveryToken: result.token, discoveredTools: result.tools, selectedTools: [] });
      showToast(`${service.name}: connection verified; choose the tools this profile may use.`, "success");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      updateService(service.key, { discovering: false });
      setPendingDiscovery(null);
    }
  }
  async function handleCreate() {
    if (!validName) { setStep("Project"); showToast("Choose a valid, unused profile name.", "error"); return; }
    if (!readyToSave) { showToast("Complete tool discovery, access review, and required credential approval first.", "error"); return; }
    setCreating(true);
    try {
      const result = await api.createNativeScienceProfile({
        name: name.trim(), config_fingerprint: options?.config_fingerprint || "", skills: selectedSkills, sources,
        services: selectedServices.map(service => {
          const draft = serviceDrafts[service.key];
          return {
            name: service.name, kind: service.kind,
            tools: service.kind === "mcp" ? draft.selectedTools : service.name === "boltzmann" ? service.tools.map(tool => tool.name) : service.tools.map(tool => tool.name),
            ...(draft.discoveryToken ? { discovery_token: draft.discoveryToken } : {}),
            approve_scope: draft.approveScope,
          };
        }),
        approve_image_download: approveImageDownload,
        approve_boltzmann_validation: approveBoltzmannValidation,
        ...(boltzmannKey.trim() ? { boltzmann_api_key: boltzmannKey.trim() } : {}),
      });
      setBoltzmannKey("");
      setCreated({ name: result.name, path: result.path });
    } catch (error) {
      showToast(`Profile creation failed: ${errorMessage(error)}`, "error");
    } finally {
      setCreating(false);
    }
  }
  async function activateCreated() {
    if (!created) return;
    try {
      const { active } = await api.setActiveProfile(created.name);
      setProfile(active);
      navigate("/chat");
    } catch (error) {
      showToast(`Profile created, but activation failed: ${errorMessage(error)}`, "error");
    }
  }

  const stepIndex = STEPS.indexOf(step);
  const canContinue = step === "Project" ? validName : step === "Tools" ? readyToSave : true;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 pb-12">
      <Toast toast={toast} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <H2>{created ? "Science profile created" : "Create science profile"}</H2>
          <p className="mt-1 text-sm text-muted-foreground">The browser follows the native CLI profile workflow. No research job runs during setup.</p>
        </div>
        {!created && <Button ghost type="button" onClick={() => navigate("/profiles")}>Cancel</Button>}
      </div>

      {created ? (
        <Card><CardContent className="space-y-5 p-6">
          <div><p className="font-medium">{created.name} is ready.</p><p className="mt-1 break-all text-sm text-muted-foreground">{created.path}</p></div>
          <p className="text-sm text-muted-foreground">Selected science skills are copied into the profile. The scientific persona is supplied automatically, the existing shared LLM login is reused, and the environment uses the reviewed source profile backend. No scientific task was run.</p>
          <div className="flex flex-wrap gap-3"><Button type="button" onClick={() => void activateCreated()}>Activate now</Button><Button outlined type="button" onClick={() => navigate("/profiles")}>Stay in current profile</Button></div>
        </CardContent></Card>
      ) : loading ? <p role="status" className="py-12 text-center text-sm text-muted-foreground">Loading available science skills and prepared services…</p> : loadError ? (
        <Card><CardContent className="space-y-3 p-5"><p role="alert" className="text-sm text-destructive">Could not load the CLI profile setup choices: {loadError}</p><Button type="button" outlined onClick={() => window.location.reload()}>Retry</Button></CardContent></Card>
      ) : options && <>
        <nav aria-label="Profile creation steps" className="grid grid-cols-5 gap-2">
          {STEPS.map((item, index) => <button key={item} type="button" onClick={() => index <= stepIndex && setStep(item)} disabled={index > stepIndex}
            className={cn("rounded border px-2 py-2 text-xs sm:text-sm", item === step ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground", index > stepIndex && "opacity-50")}>
            {index + 1}. {item}
          </button>)}
        </nav>

        <Card><CardContent className="space-y-5 p-5 md:p-6">
          {step === "Project" && <div className="space-y-5">
            <div className="space-y-1.5"><Label htmlFor="science-profile-name">Science profile name</Label><Input id="science-profile-name" autoFocus placeholder="antibody-project" value={name} onChange={event => setName(event.target.value)} />
              {name && !validName && <p className="text-xs text-destructive">Use lowercase letters, digits, hyphens, or underscores; do not use main/default.</p>}
              <p className="text-xs text-muted-foreground">A new profile starts with separate history, skills, tools, and project workspace. Existing profiles are never overwritten.</p>
            </div>
            <div className="border-t border-border pt-4"><p className="text-sm font-medium">Scientific persona</p><p className="mt-1 text-sm text-muted-foreground">{options.persona}</p></div>
            <p className="text-sm text-muted-foreground">LLM credentials are shared through the existing Sci login. You do not need to sign in again for this profile.</p>
          </div>}

          {step === "Science skills" && <div className="space-y-4">
            <div><h3 className="font-medium">Choose scientific skills</h3><p className="text-sm text-muted-foreground">Only installed science-related skill instructions are offered. Selected skills are copied into this profile; nothing is executed during selection.</p></div>
            <Input aria-label="Filter science skills" placeholder="Filter by skill or description…" value={skillFilter} onChange={event => setSkillFilter(event.target.value)} />
            {filteredSkills.length ? <div className="max-h-[55vh] space-y-1 overflow-y-auto rounded border border-border p-2">
              {filteredSkills.map(skill => <label key={skill.name} className="flex cursor-pointer items-start gap-3 rounded px-2 py-2 hover:bg-muted/40">
                <Checkbox checked={selectedSkills.includes(skill.name)} onCheckedChange={() => toggleSkill(skill.name)} />
                <span className="min-w-0 flex-1"><span className="font-medium">{skill.name}</span><span className="ml-2 text-xs text-muted-foreground">{skill.origin}</span><span className="block text-xs text-muted-foreground">{skill.description}</span></span>
              </label>)}
            </div> : <p className="rounded border border-border p-4 text-sm text-muted-foreground">No science skills are available in this installation. You can still create the profile.</p>}
            <p className="text-xs text-muted-foreground">{selectedSkills.length} selected. Setup still applies to software prerequisites; skills do not install research software.</p>
          </div>}

          {step === "Tools" && <div className="space-y-4">
            <div><h3 className="font-medium">Choose services and tools</h3><p className="text-sm text-muted-foreground">MCP tools require an approved handshake and explicit per-tool selection. Plugins grant their complete listed permission scope.</p></div>
            <Input aria-label="Filter services" placeholder="Filter services…" value={serviceFilter} onChange={event => setServiceFilter(event.target.value)} />
            <div className="space-y-3">
              {filteredServices.map(service => {
                const draft = serviceDrafts[service.key] || emptyServiceDraft;
                const canSelect = service.ready || service.name === "boltzmann";
                return <section key={service.key} className="rounded border border-border p-4">
                  <div className="flex items-start gap-3">
                    <Checkbox checked={draft.selected} disabled={!canSelect} onCheckedChange={value => toggleService(service, Boolean(value))} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><h4 className="font-medium">{service.name}</h4><Badge tone="secondary">{service.kind === "mcp" ? "MCP" : "Plugin"}</Badge>{service.transport && <Badge tone="secondary">{service.transport === "local" ? "Runs locally" : "Remote service"}</Badge>}</div>
                      <p className="mt-1 text-sm text-muted-foreground">{service.description}</p>
                      {service.destination && <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{service.destination}</p>}
                      {service.reason && <p className={cn("mt-2 text-xs", service.name === "boltzmann" ? "text-muted-foreground" : "text-amber-300")}>{service.reason}</p>}
                      {!service.ready && service.name !== "boltzmann" && <p className="mt-1 text-xs text-muted-foreground">Set this connection up on the MCP/Plugins page, then refresh this wizard.</p>}
                    </div>
                  </div>
                  {draft.selected && service.kind === "mcp" && <div className="ml-7 mt-4 space-y-3">
                    <Button type="button" outlined disabled={draft.discovering} onClick={() => setPendingDiscovery(service)}>{draft.discovering ? "Connecting and discovering…" : draft.discoveryToken ? "Rediscover tools" : "Connect and discover tools"}</Button>
                    {draft.discoveryToken && <p role="status" className="text-xs text-emerald-300">Connection verified. No business tools were called. Select the tools this profile may access:</p>}
                    {draft.discoveredTools.map(tool => <label key={tool.name} className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-muted/40">
                      <Checkbox checked={draft.selectedTools.includes(tool.name)} onCheckedChange={() => toggleTool(service, tool.name)} />
                      <span className="min-w-0"><span className="font-medium">{tool.name}</span><span className="block text-xs text-muted-foreground">{tool.description}</span></span>
                    </label>)}
                    {draft.discoveryToken && !draft.discoveredTools.length && <p className="text-xs text-destructive">No tools were returned. This service cannot be added with an empty allowlist.</p>}
                  </div>}
                  {draft.selected && service.kind === "plugin" && <div className="ml-7 mt-4 space-y-3">
                    {service.name === "boltzmann" ? <>
                      <p className="text-sm text-muted-foreground">Boltzmann requires an authorized API key. Its submit, status, upload, download, and tool-log helper operations are included together; this is plugin-wide access.</p>
                      {!service.credential_ready && <div className="space-y-1.5"><Label htmlFor="profile-boltzmann-key">Boltzmann API key</Label><Input id="profile-boltzmann-key" type="password" autoComplete="new-password" value={boltzmannKey} onChange={event => setBoltzmannKey(event.target.value)} placeholder="Enter key (masked)" /></div>}
                      {service.credential_ready && <div className="space-y-1.5"><Label htmlFor="profile-boltzmann-key">Use another key (optional)</Label><Input id="profile-boltzmann-key" type="password" autoComplete="new-password" value={boltzmannKey} onChange={event => setBoltzmannKey(event.target.value)} placeholder="Leave blank to use the saved key" /></div>}
                      <label className="flex items-start gap-2 text-xs"><Checkbox checked={draft.approveScope} onCheckedChange={value => updateService(service.key, { approveScope: Boolean(value) })} /><span>I approve the complete Boltzmann plugin scope for this profile. Its tools are available together; access is not isolated per scientific operation.</span></label>
                      <label className="flex items-start gap-2 text-xs"><Checkbox checked={approveBoltzmannValidation} onCheckedChange={value => setApproveBoltzmannValidation(Boolean(value))} /><span>Approve read-only API-key validation with Boltzmann before profile creation. No scientific job will be submitted.</span></label>
                    </> : <>
                      <p className="text-sm text-amber-200">Plugin access is granted at plugin level. The profile cannot isolate these tools one by one.</p>
                      <ul className="list-disc pl-5 text-xs text-muted-foreground">{(service.capabilities || []).map(capability => <li key={capability}>{capability}</li>)}</ul>
                      <label className="flex items-start gap-2 text-xs"><Checkbox checked={draft.approveScope} onCheckedChange={value => updateService(service.key, { approveScope: Boolean(value) })} /><span>I approve the complete permission scope above for this profile.</span></label>
                    </>}
                  </div>}
                </section>;
              })}
              {!filteredServices.length && <p className="rounded border border-border p-4 text-sm text-muted-foreground">No prepared integrations are available. Add/configure an MCP server or plugin first; this wizard will not invent a connector.</p>}
            </div>
            {selectedServices.length > 0 && incompleteServices.length > 0 && <div role="status" className="rounded border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100">
              <p className="font-medium">Complete these access steps before continuing:</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">{incompleteServices.map(issue => <li key={issue}>{issue}</li>)}</ul>
            </div>}
            <p className="text-xs text-muted-foreground">Selected service connections are copied into the new profile only after final review. Existing profile configuration is unchanged.</p>
          </div>}

          {step === "Sources" && <div className="space-y-4">
            <div><h3 className="font-medium">Add project sources (optional)</h3><p className="text-sm text-muted-foreground">Provide local file/folder paths or public HTTPS URLs. Adding a source does not read, download, index, or upload it.</p></div>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Source type">
              {([ ["path", "Local path"], ["url", "HTTPS URL"] ] as const).map(([value, label]) => <Button key={value} type="button" size="sm" outlined={sourceKind !== value} onClick={() => { setSourceKind(value); if (value === "url") setSourceAccess("reference"); }}>{label}</Button>)}
            </div>
            <div className="grid gap-3 md:grid-cols-[1fr_260px_auto]">
              <div className="space-y-1.5"><Label htmlFor="profile-source-location">{sourceKind === "path" ? "Path on the Sci host" : "Public HTTPS URL"}</Label><Input id="profile-source-location" value={sourceLocation} onChange={event => setSourceLocation(event.target.value)} placeholder={sourceKind === "path" ? "/data/project/reference.pdb" : "https://www.rcsb.org/…"} /></div>
              <div className="space-y-1.5"><Label htmlFor="profile-source-access">Access for this profile</Label><select id="profile-source-access" className="h-10 w-full rounded border border-border bg-background px-3 text-sm" value={sourceAccess} onChange={event => setSourceAccess(event.target.value as SourceAccess)}>
                <option value="reference">Reference only</option>{sourceKind === "path" && <><option value="read-local">Allow local reading/processing</option><option value="model">Allow relevant contents to selected model</option></>}
              </select></div>
              <div className="flex items-end"><Button type="button" outlined onClick={addSource} disabled={!sourceLocation.trim()}>Add source</Button></div>
            </div>
            {sources.length > 0 ? <div className="space-y-2">{sources.map((source, index) => <div key={`${source.location}-${index}`} className="flex flex-wrap items-center gap-3 rounded border border-border px-3 py-2 text-sm"><span className="min-w-0 flex-1 break-all font-mono text-xs">{source.location}</span><Badge tone="secondary">{source.access}</Badge><Button type="button" size="sm" ghost onClick={() => setSources(items => items.filter((_, itemIndex) => itemIndex !== index))}>Remove</Button></div>)}</div> : <p className="rounded border border-dashed border-border p-4 text-sm text-muted-foreground">No project sources added.</p>}
            <p className="text-xs text-muted-foreground">Reference-only content is not read. Local-reading access permits local processing only. Model access allows relevant contents to the selected model, not arbitrary external services. Original files are never modified.</p>
          </div>}

          {step === "Review" && <div className="space-y-5">
            <div><h3 className="font-medium">Review science profile</h3><p className="text-sm text-muted-foreground">The profile is published only after you create it. Nothing in the current conversation is changed.</p></div>
            <dl className="grid gap-3 rounded border border-border p-4 text-sm md:grid-cols-[150px_1fr]">
              <dt className="text-muted-foreground">Name</dt><dd>{name}</dd>
              <dt className="text-muted-foreground">Science skills</dt><dd>{selectedSkills.length ? selectedSkills.join(", ") : "None"}</dd>
              <dt className="text-muted-foreground">Services/tools</dt><dd>{selectedServices.length ? selectedServices.map(service => {
                const count = serviceDrafts[service.key]?.selectedTools.length || 0;
                return service.kind === "mcp" ? `${service.name} (${count ? `${count} selected tools` : "no tools selected — setup incomplete"})` : `${service.name} (plugin-wide access)`;
              }).join("; ") : "None"}</dd>
              <dt className="text-muted-foreground">Sources/access</dt><dd>{sources.length ? sources.map(source => `${source.location} [${source.access}]`).join("; ") : "None"}</dd>
              <dt className="text-muted-foreground">Environment</dt><dd>{options.environment.backend}{options.environment.backend === "docker" && options.environment.docker_image ? ` · ${options.environment.docker_image}` : ""}</dd>
              <dt className="text-muted-foreground">Persona/login</dt><dd>Scientific persona supplied automatically · shared LLM login reused</dd>
            </dl>
            {options.environment.backend === "local" && <p className="rounded border border-amber-400/30 bg-amber-400/5 p-3 text-xs text-amber-100">Local execution uses the host's existing software and a separate workspace. This is profile separation, not OS-level filesystem isolation. No software is installed.</p>}
            {options.environment.backend === "docker" && <label className="flex items-start gap-2 rounded border border-border p-3 text-sm"><Checkbox checked={approveImageDownload} onCheckedChange={value => setApproveImageDownload(Boolean(value))} /><span>Approve downloading the configured Docker image if it is missing. Downloaded layers may remain if creation is cancelled.</span></label>}
            {!readyToSave && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100">
              <div><p className="font-medium">Profile setup is incomplete:</p><ul className="mt-1 list-disc pl-5">{incompleteServices.map(issue => <li key={issue}>{issue}</li>)}</ul></div>
              <Button type="button" outlined onClick={() => setStep("Tools")}>Return to Tools</Button>
            </div>}
            <p className="text-xs text-muted-foreground">Existing configuration and history stay unchanged. Missing scientific software does not block saving; prerequisites are reported for setup. No research job will be run.</p>
          </div>}

          <div className="flex items-center justify-between border-t border-border pt-4">
            <Button type="button" ghost disabled={stepIndex === 0 || creating} onClick={() => setStep(STEPS[stepIndex - 1])}>Back</Button>
            {step !== "Review" ? <div className="flex flex-col items-end gap-1"><Button type="button" disabled={!canContinue} onClick={() => setStep(STEPS[stepIndex + 1])}>Continue</Button>{step === "Tools" && !canContinue && <span className="text-right text-xs text-muted-foreground">Complete the selected services above first.</span>}</div> : <Button type="button" disabled={!readyToSave || creating || !validName} onClick={() => void handleCreate()}>{creating ? "Creating profile…" : "Create profile"}</Button>}
          </div>
        </CardContent></Card>
      </>}

      {pendingDiscovery && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setPendingDiscovery(null); }}>
        <section role="dialog" aria-modal="true" aria-labelledby="profile-discovery-title" className="w-full max-w-lg space-y-4 border border-border bg-card p-5 shadow-2xl">
          <h3 id="profile-discovery-title" className="font-medium">Review MCP connection</h3>
          <p className="text-sm">Sci will connect to <strong>{pendingDiscovery.name}</strong> at:</p>
          <p className="break-all rounded border border-border bg-background p-3 font-mono text-xs">{pendingDiscovery.destination}</p>
          {pendingDiscovery.transport === "local" && <p className="text-sm text-amber-200">This starts a local MCP process. It may execute installed software or a package runner. Approve only if you trust this configured command.</p>}
          <p className="text-sm text-muted-foreground">The check performs an MCP handshake and lists tool metadata only. It does not call business tools or send research data. Existing connection credentials are used; secrets are not shown.</p>
          <div className="flex justify-end gap-2"><Button type="button" ghost onClick={() => setPendingDiscovery(null)}>Cancel</Button><Button type="button" onClick={() => void discover(pendingDiscovery)}>Approve and discover</Button></div>
        </section>
      </div>}
    </div>
  );
}
