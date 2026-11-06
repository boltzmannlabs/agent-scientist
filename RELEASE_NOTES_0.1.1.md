# Agent Scientist 0.1.1 Release Notes

Agent Scientist 0.1.1 introduces reusable scientific specialists, portable specialist packages, private specialist capabilities, side conversations, and persistent monitoring of Boltzmann jobs. Together, these features help teams preserve research instructions, share reviewed workflows, discuss related questions during ongoing work, and follow long-running calculations beyond a single terminal session.

## 1. Reusable specialist subagents

Create a named specialist once and reuse its instructions, capabilities, and expected output across assignments. A specialist can focus on a recurring responsibility such as literature review, dataset inspection, or scientific report preparation, giving subsequent tasks a consistent starting point.

Each saved specialist defines its purpose, scientific skills or modules, allowed tools, additional instructions, optional reference locations, and expected output. The guided creation flow brings these choices together for review before saving. Instructions can be supplied as text or loaded from a supported local instruction file, allowing teams to reuse their established working procedures.

Specialists can be created directly in main or within a research profile. They use the owning profile's model authentication and delegation configuration, so creating a specialist does not require another Agent Scientist installation or a separate LLM login. Definitions and run history remain scoped to their owning profile.

Users can assign a specialist explicitly or name it in an ordinary conversation. New specialists also support automatic matching, allowing the model to select a relevant specialist when interpreting a task. Automatic matching is model-driven; explicit assignment remains available when the user wants a particular specialist involved.

```text
/Create_subagent literature-reviewer
/new
/subagent run literature-reviewer "Compare these supplied abstracts and identify their limitations"
```

`/Update_subagent` opens existing definitions for review and editing, while `/subagents` provides a searchable management view. Run status and history retain available results, errors, and transcript locations. For a live run owned by the current conversation, users can request cancellation or send a course correction through the stop and steer commands.

Tool permissions are checked during execution. Selecting a skill supplies instructions; it does not authorize a service or grant additional tool access. Saved definition changes apply to a new conversation, preserving the active conversation's prompt and tool configuration.

## 2. Portable specialist packages

Portable packages let teams distribute a reviewed specialist across profiles and servers with the resources and dependency declarations needed to recreate its setup. This supports a repeatable contribution and installation process for shared research assistants.

A package describes the specialist's identity, version, purpose, instructions, output requirements, permitted tools, and scientific skills. It can include complete custom skill resources, approved reference material, supported-platform information, dependency requirements, and verification fixtures. Attribution and licensing information accompany the package so recipients can review both its intended use and redistribution terms.

Installation presents the destination and required setup for review. Agent Scientist resolves resources in the receiving environment and requests any necessary service authentication or capability approvals. Credentials, authorization receipts, conversations, and run history are not distributed with the package. The receiving user establishes their own access to protected services.

```text
/subagent package
/subagent package install "/path/to/reviewed-specialist-package"
/new
/subagent run literature-reviewer "Review the supplied papers"
```

Packages with missing required dependencies or incomplete authentication remain in a setup-required state. Their specialist stays disabled until the required setup and review are complete. Verification fixtures provide reviewable examples and expected results; installation readiness does not establish the scientific correctness of every future assignment.

Package updates are explicit and reviewed. Users can inspect available catalog updates before applying them, and updated definitions take effect in a new conversation. Existing histories and shared software are preserved. Catalog entries become available as reviewed contributions are included; this feature does not imply a preinstalled collection of specialist packages.

The existing definition-only export and import commands remain available for simpler transfers. Packages support the fuller distribution case, where a specialist also needs declared dependencies, supporting skills, or approved resources.

## 3. Specialist-specific capabilities

A specialist can now receive capabilities in its own private destination. Teams can equip a particular assistant for its assigned work while keeping its additions separate from the capability lists and connection settings of main, other profiles, and sibling specialists.

During creation or editing, **Add for this subagent only** provides access to the supported setup flows:

- **Skills:** add prepared skill files or bundles, retaining their supporting resources.
- **Tools and plugins:** submit a tool source or integration request through the existing reviewed setup process.
- **MCP connections:** configure a service, complete supported authentication and connection discovery, and select its permitted tools.
- **Existing local programs:** describe an installed executable or script, its invocation, inputs, outputs, and limitations for use during an assignment.

Private additions appear in the specialist's review before saving. A specialist may combine them with selected capabilities already available from its owning profile. Inherited service tools continue to use the owning profile's authorization, while private connections keep their own reviewed configuration and credential storage. Model access continues through the owning agent's resolved LLM authentication.

The private destination separates configuration and capability exposure. Execution still follows the configured backend, tool permissions, and approval rules; private storage does not itself provide an operating-system sandbox. Boltzmann operations continue to require valid authorization in the owning scope.

Removing a private capability removes its selected grant without automatically deleting retained software or credentials. Newly saved additions become available in a fresh conversation, allowing users to review capability changes without silently altering an ongoing assignment.

## 4. Side conversations

Use `/side` to explore a separate question while the main task continues. This is useful when a researcher wants to clarify terminology, discuss an interpretation, or consider a related approach without redirecting the active task.

The side conversation starts from a snapshot of completed context available when it is opened. This gives it relevant background while maintaining its own exchange of messages. Later main-task progress is not continuously injected into that snapshot.

```text
/side
```

Side messages remain separate from the main transcript. The main task retains its existing conversation state, and discussing an alternative in the side conversation does not automatically rewrite the main task's instructions. Users can continue the separate discussion and return to the main task when ready.

This separation preserves the main conversation's cached prompt and avoids inserting unrelated exchanges into its working history. Side conversations still use model requests and remain subject to the applicable tools, permissions, and execution approvals.

## 5. Persistent scientific-job monitoring

Accepted Boltzmann jobs now receive durable monitoring records, allowing Agent Scientist to track long-running calculations beyond the lifetime of the initiating terminal session. Each record preserves the existing job identity and the information needed to continue checking that job.

Monitoring distinguishes pending and running work from confirmed terminal outcomes. Temporary connectivity or authorization problems are recorded as monitoring problems rather than being treated as proof that the scientific calculation failed. Subsequent checks continue against the existing job ID; resuming monitoring does not submit a replacement calculation.

Background workers can continue after the terminal closes. If the host shuts down, monitoring records remain available, and checks can resume when the owning SCI session starts or through the resume command. Polling cannot continue while the host is offline, and this feature does not install an operating-system startup service.

Users can inspect and control monitoring from the CLI:

```bash
sci boltzmann-jobs status
sci boltzmann-jobs status job:<monitor-id>
sci boltzmann-jobs stop job:<monitor-id>
sci boltzmann-jobs resume job:<monitor-id>
```

Status information includes retained results, recent checks, monitoring failures, and any continuation report. Stopping a monitor stops its monitoring and future continuation; it does not cancel a calculation already running on the remote platform. Reports remain available for inspection when the original conversation is closed or offline.

For supported native workflows with a saved approval checkpoint, Agent Scientist can continue remaining approved work after the linked jobs reach confirmed terminal states. This can include collecting and checking results or carrying out the next approved step. Continuation uses the originating task's allowed tools together with the owning profile's current permissions. Missing inputs, additional permissions, or new charges requiring approval return the workflow to user review.

Monitoring and continuation preserve profile ownership and use the profile's current authorization. They do not obtain access from another profile, silently switch providers, or repeat an ambiguous submission. The original conversation remains intact, with continuation outcomes retained separately for review.
