---
name: sales-play-selection
description: >-
  Guides selecting the appropriate sales play based on customer context such as industry and practice area.
  Use when a user asks to recommend or select a sales play for a specific customer or scenario.
---

# Sales Play Selection

## Overview

This skill helps the agent select the right sales play from the available list
based on customer criteria (Industry, Practice Area).

## Sales Play Selection Guidelines

To select the appropriate sales play, follow these steps:

1.  **Identify Customer Industry**: Determine the customer's industry if
    available (e.g., Retail, Healthcare, Financial Services).
2.  **Identify Practice Area**: Determine the relevant practice area (AI, Data,
    Infrastructure, Security, Agentic Workplace Transformation).
3.  **Consult List**: Look up the matching sales plays in the **Available Sales
    Plays** section below.
4.  **Select Best Fit**:
    -   If a play matches both Industry and Practice Area, select it.
    -   If no industry-specific play matches, select the general play for that
        Practice Area (where industry is empty).
    -   If multiple match, list them and ask for clarification or select the
        most specific one.

### Tips & Gotchas

-   **Do this**: Always check for industry-specific plays first. They are more
    tailored and usually preferred.
-   **Not that**: Don't just pick the first play that matches the practice area
    without checking if an industry-specific one exists.
-   **Watch out for**: Some plays have very similar names but different IDs.
    Always verify the ID when performing actions that require the ID.
-   **Clarification**: If the customer context is ambiguous, ask the user to
    clarify the industry or practice area rather than guessing.
-   **AI Plays**: For AI-specific plays, use the
    [AI Sales Play Decision Tree](references/ai_sales_play_decision_tree.md) to
    guide your selection based on specific customer needs.

## Available Sales Plays

### Play Types

-   **Primary**: Full field activation.
-   **Growth**: Targeted, list-based accounts.
-   **Emerging**: Targeted small list-based activation for experimental and
    emerging markets.

### Agentic Workplace Transformation

-   **Lead the Agentic Workplace Transformation** [Primary]
    -   The main AWT play which includes Gemini Enterprise and Google Workspace.
        Provides secure and innovative platforms to help organizations reimagine
        the way collaboration and work can be done with AI at the individual,
        team, and organization-wide level, all while improving the quality of
        work and maintaining enterprise grade security.
-   **Lead the Agentic Workplace Transformation - Gemini Enterprise** [Primary]
    -   The AWT play focusing on Gemini Enterprise.
-   **Lead the Agentic Workplace Transformation - Google Workspace** [Primary]
    -   The AWT play focusing on Google Workspace.

### AI

-   **Gemini Enterprise for Customer Experience** [Growth]
    -   A unified agentic solution that transforms fragmented search, commerce
        and service interactions into a seamless customer journey that drives
        growth.
-   **Gemini Enterprise for Customer Experience - Customer Service** [Growth]
-   **Leverage Generative Media in Your Business** [Growth]
    -   A comprehensive approach to customers with our Generative Media models
        (Gemini, Imagen, Veo and other models). Generative Media is distinct in
        that the market opportunity lies in customer segments that are serving
        billions of end users through experiences and with their content
        generation and editing tools as well as enterprise customers that
        generate content for consumer experiences.
-   [**Scale AI Apps and Agents**](references/scale_ai_apps_and_agents.md)
    [Primary]
    -   Enable customers and partners to build, deploy, and manage the full
        spectrum of AI applications and agents on Gemini Enterprise, driving
        adoption and API consumption by leading with flexible model choice (1P,
        3P, OSS) and the power of agents.
-   **Your Business, Your Models** [Growth]
    -   Targeted at Model Builders and AI-First Enterprises that are adopting
        Gen AI models (1P, 3P, OSS) and need to tune and train the models to
        meet specific business needs and/or develop monetizable products, to
        create a unique, defensible, and competitive asset.

### Data

-   **Agentic Data Cloud** [Primary]
    -   Help customers activate their data estate on an unified, intelligent,
        self-managing platform to power agentic experiences, accelerate data
        science, and activate new intelligent business outcomes.
-   **Migrate, Modernize, and Build with Data Cloud** [Primary]
    -   Accelerates customers' AI transformation by positioning Google Cloud's
        Data Cloud (AI-powered Databases and Analytics) as the unified platform
        for their entire data estate — whether they are migrating from
        on-premises or other clouds, or modernizing their core applications.

### Infrastructure

-   **AI Infrastructure** [Growth]
    -   Targeted GTM play with differentiated offerings for select industries,
        focusing on relevant use cases and priority areas across FSI, Gaming,
        Life Sciences, Manufacturing, M&E, and Retail.
-   **Enterprise Platform of Choice: Oracle** [Growth]
    -   Seamless Oracle experience on Google Cloud that simplifies cloud
        adoption, providing choices in deployments. Providing procurement
        simplicity with the highest security posture that is fully integrated
        with existing ecosystems.
-   **Enterprise Platform of Choice: SAP** [Growth]
    -   Enhance migrated SAP workloads on GCP, transforming infrastructure with
        innovative services like BigQuery for analytics and Gemini Enterprise
        for AI/ML.
-   **Enterprise Platform of Choice: VMware** [Growth]
    -   Targeted play to migrate and run existing VMware workloads on GCP
        seamlessly, without requiring significant changes to their applications,
        tools, or processes.
-   **Enterprise Storage (GCNV)** [Emerging]
    -   Google Cloud NetApp Volumes enables the seamless "lift and shift" of
        enterprise workloads like Oracle, SAP, and VMware without refactoring.
        It establishes an AI-ready foundation by connecting this proprietary
        data directly to Gemini Enterprise to unlock immediate business
        insights.
-   **Google Distributed Cloud (GDC)** [Emerging]
    -   A fully managed software and hardware solution for data centers and edge
        locations to address regulatory, local data processing, survivability,
        and low-latency needs. It comes in two flavors (GDC air-gapped and GDC
        connected) plus a Gemini overlay.
-   **High Performance Computing (HPC)** [Emerging]
    -   Help customers accelerate innovation and business insights. We do this
        by providing easy-to-deploy, open-standards HPC solutions, complete with
        industry-specific workload blueprints. This approach builds credibility
        with our customers, shortens their time to production on Google Cloud,
        and ultimately increases our wallet share from HPC migrations.
-   **Managed Global WAN (Cloud WAN)** [Emerging]
    -   A fully managed global backbone built on Google's planet-scale network
        to unify enterprise connectivity for the AI era. It consolidates complex
        legacy networks into a single solution that delivers high-performance
        site-to-site connectivity and secure branch-to-cloud migration.
-   **Migrate, Modernize and Build** [Primary]
    -   A holistic migrations full-field play to quickly evaluate customer
        environment and develop a migration plan across diverse workloads to
        GCP.
-   **Modern Compute (ARM)** [Emerging]
    -   Offers efficiency and cost advantages for various use cases and
        workloads, including web servers, databases, and media streaming,
        enabling competitive takeout of AWS Graviton and other Arm-based
        solutions. This enhanced price-performance also boosts competitiveness
        in greenfield segments.
-   **Sovereign** [Growth]
    -   Full field and targeted play to offer choice and security through
        options like Data Boundary, Dedicated Cloud, and Air-Gapped solutions
        that avoid restrictive licensing.

### Security

-   **Achieve Resilience Together with Mandiant** [Growth]
    -   A targeted sales play providing guidance on how to attach Mandiant
        Consulting's strategic security transformation and incident response
        capabilities before, during and after key customer security moments.
-   **Agentic Defense with Google Security** [Primary]
    -   An advanced approach to cybersecurity that uses autonomous,
        goal-oriented AI systems to proactively and independently detect,
        investigate, and respond to cyber threats.
-   **Cybershield** [Emerging]
    -   An advanced approach to cybersecurity that uses autonomous,
        goal-oriented AI systems to proactively and independently detect,
        investigate, and respond to cyber threats.
-   **Secure Innovation with Google Cloud** [Primary]
    -   Empowering organizations to accelerate AI, Data, and Cloud migrations
        confidently by integrating security from inception, enabling
        frictionless growth and trusted innovation on Google Cloud.
-   **SOC Transformation** [Growth]
    -   An advanced approach to cybersecurity that uses autonomous,
        goal-oriented AI systems to proactively and independently detect,
        investigate, and respond to cyber threats.
