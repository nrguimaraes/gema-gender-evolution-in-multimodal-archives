## **GEMA: Gender Evolution in Multimodal Archives** 

_Technical Report on Analytical Pipeline Development and Integration_ 

## **1. Introduction** 

## **1.1. Background and Motivation** 

Gender representation in sports journalism has historically been characterised by a profound asymmetry, in which men's sport dominates not only in volume of coverage but also in editorial prominence — front pages and depth of narrative. In Portugal, the sports media agenda is shaped by the three major print sports dailies (A Bola, Record, and O Jogo), as well as general-interest newspapers and digital-native portals (Sapo Desporto, MaisFutebol, Notícias ao Minuto). 

Despite growing social demand for parity and the sustained rise of women's sport, objectively measuring this evolution over time requires advanced data analysis tools. Traditional media studies have relied on manual sampling, inherently limited in scale. This project addresses the need to automate the auditing of journalistic digital memory by applying Artificial Intelligence to analyse a massive, longitudinal corpus spanning nearly three decades (1998–2024). 

## **1.2. Project Objectives** 

This internship focused on the development and integration of GEMA, a multimodal computational pipeline designed to quantify gender representation in Portuguese sports media. The specific objectives were: 

- Data Extraction and Storage: Design a scalable database infrastructure to aggregate thousands of articles and associated metrics, moving beyond the fragility of static files. 

- Visual and Textual Processing: Integrate Computer Vision models (athlete detection) and Natural Language Processing (NLP) for entity extraction and gender identification, supported by census-based reference databases. 

- Longitudinal Analysis: Examine journalistic impact over time (1998–2024) and assess whether major sporting events function as catalysts for greater representational equity. 

- Interactive Demonstrator: Structure the data to feed a future web-based analytical dashboard. 

## **2. Methodology: The Multimodal Pipeline** 

To address the research questions, an architecture was designed capable of processing both the Visual Axis (front pages) and the Textual Axis (news articles and leads). 

## **2.1. Data Architecture and Textual Crawler Development** 

Textual data extraction relied on the Arquivo.pt API to access historical snapshots of the three main national sports dailies. Given the dramatic evolution of web architectures over nearly three decades — from primitive markup (tables, <font> tags and frames in 1998–2005) to ASP.NET dynamic pages and, more recently, JavaScript-based reactive frameworks such as Next.js — the construction of the Python crawlers (using requests and BeautifulSoup) demanded a modular, highly adaptive design. 

To manage this complexity, an architecture based on the Router Design Pattern was implemented. A central dispatch function (getArticle) was developed to dynamically evaluate the origin (domain) and temporal timestamp (year) of each candidate URL, routing processing to dedicated extractors tailored to the "technological era" of each portal. The extraction pipeline was structured to ensure maximum resilience at scale: 

- Phase-based Iterative Separation: The process was divided into Phase 1 (extraction and storage of candidate links by year and source) and Phase 2 (raw HTML processing and article content extraction). This compartmentalisation allowed safe process resumption — skipping alreadyprocessed files — in the event of connection losses. 

- Latency Control and Timeout Management: Given the inherent instability of querying the petabyte-scale Arquivo.pt database (frequently generating ReadTimeout errors or network failures), scripts were equipped with optimised wait times and randomised sleep intervals to mimic human browsing behaviour and avoid server-side blocking. 

- Dynamic Deduplication: A runtime verification mechanism based on URLs (rather than titles alone) was implemented to avoid redundancies created by the daily homepage updates captured in snapshots. 

- Storage Evolution: The initial reliance on local JSON files was superseded by a non-relational database, structured via a dedicated Python client (SportGenDB) connected to MongoDB. Iterative asynchronous writes guaranteed data integrity across multiple extraction runs through a strict unique index. 

## **2.2. Visual Axis: Front-Page Extraction, Athlete Detection and Visual Prominence** 

The original image extraction strategy via Arquivo.pt screenshots proved inadequate, frequently returning low-resolution images, corrupted files, or iframe loading failures. To ensure analytical rigour, the visual extraction strategy was redirected to the dedicated front-page repository vercapas.com. The crawler was configured to bypass preview thumbnails by dynamically substituting the URL directory (/thumbc/ to /covers/), thereby retrieving covers at maximum resolution. 

To quantify visual prominence on sports daily front pages, a hybrid Computer Vision approach was adopted, combining whole-body detection with detailed facial analysis: 

- Global Presence Detection (YOLOv8): The YOLOv8 Nano model (yolov8n.pt) was applied to filter and identify the "person" class, providing total body counts and bounding boxes — including cases in which athletes appear from behind or with occluded faces. 

- Facial Recognition and Gender Prediction (DeepFace / RetinaFace): In parallel, the RetinaFace detector (via the DeepFace library) analysed RGBconverted images to identify faces with high confidence and predict the dominant gender (male or female). 

- Relative Prominence Metric: RetinaFace enabled computation of the cover_coverage_percentage — the proportion of the image area occupied by a detected face's bounding box. This metric is critical for assessing whether female athletes receive equivalent visual prominence to their male counterparts. 

- Fusion and Final Verdict: By cross-referencing the outputs of both models, the system computes "Indeterminate" presences (the difference between total bodies detected by YOLO and faces classified by RetinaFace). The pipeline then assigns an overall verdict to each cover: "Male", "Female", "Mixed/Balanced", or "Indeterminate". 

## **2.3. Textual Axis: Named Entity Recognition and Gender Disambiguation** 

Semantic extraction was based on a two-phase architecture: 

- Named Entity Recognition (NER): Transformer-based models (rooted in BERTimbau/WikiNeural) were used to isolate the protagonists of each article. 

- Lexical Matching via Census Data: For gender disambiguation, extracted entities were cross-referenced against an external census-based first names database (firstnames.csv). This deterministic approach enabled fast, highreliability classification prior to submitting ambiguous cases for advanced inference. 

## **2.4. Analytical Segmentation and Structural Events** 

Data were segmented chronologically (1998–2024), with particular attention to the "Olympic Effect". A binary flag was created to isolate Olympic years (e.g., 2000, 2004, 2016, 2024) from standard years, enabling hypothesis testing around atypical spikes in media parity driven by national athletic delegations. 

## **2.5. Data Cleaning and Noise Engineering** 

The historical Arquivo.pt sites exhibited extreme structural mutations across decades (broken navigation menus, obsolete advertisements). The manual content-cutting approach was replaced and optimised through the following strategies: 

- Trafilatura for Boilerplate Removal: This library automatically identified the main editorial text body (lead and article), discarding navigation menus and footers regardless of legacy CSS classes. 

- Density Filtering and Deduplication: A digit-ratio filter was retained to discard league tables, and a composite key (source + title) was used to retain only the most complete version of articles duplicated across different crawl runs. 

## **2.6. The Textual Classification "Complexity Ladder"** 

The pipeline adopted successive validation layers to address the "false feminine" institutional problem — terms such as "a equipa" (the team) or "a seleção" (the national squad) being grammatically feminine in Portuguese while referring to male-dominated contexts: 

- Lexical Matching (Census Baseline): Direct mapping of extracted names against the firstnames.csv file. Fast, but unable to handle isolated pronouns. 

- Stanza / SpaCy: Deep morphological analysis to capture control pronouns and basic grammatical structuring. 

- WikiNeural: Exclusive focus on validating named entities of type Person (PER), anchoring the article to the real subject rather than the club or institution. 

- mDeBERTa-v3: Zero-shot semantic evaluation at paragraph level, classifying neutral or shared contexts as "Both". 

- GPT-4o (Pragmatic LLM): Resolution of complex disambiguations using business rules and world knowledge, returning structured JSONs with gender classification and justification for each article lead. 

## **3. Results and Discussion** 

## **3.1. Comparative Model Performance Analysis** 

Experiments across temporal subsets revealed significant nuances inherent to sports language: 

- The Lexical Trap: Simple word-count baselines produced critical biases due to the prevalence of grammatically feminine institutional terms ("a formação", "a equipa") in predominantly male contexts. 

- The Transformers/Census Balance: The symbiosis between NER (WikiNeural) and census-based mapping proved highly effective at stabilising gender identifications, outperforming morphological analysis alone (Stanza). 

- The Semantic Ceiling: GPT-4o was the only model consistently immune to false positives arising from sports-specific jargon, making it essential for auditing ambiguous articles. 

## **3.2. Technical Limitations and Infrastructure Engineering** 

- GPT-4o API Stability: Switching from streaming to synchronous requests with forced JSON formatting eliminated recurring JSONDecodeError exceptions and ensured MongoDB record integrity. 

- Historical Layout Resilience: Replacing static CSS selectors with the Trafilatura library overcame the programmatic ad injection prevalent post2015, cleanly isolating article leads for AI analysis. 

- Visual Extraction Refactoring: The initial strategy of collecting front-page images via the Arquivo.pt API encountered severe resolution issues and graphic data loss due to inactive legacy scripts. The solution required building an independent scraping module targeting the high-resolution repository VerCapas (2016–2026). To prevent server-side blocking during large-scale daily extractions, a stealth strategy was integrated — injecting randomised latency intervals (sleep intervals of 1 to 20 seconds) to simulate human navigation. This architectural change, followed by JSON file consolidation into MongoDB, was critical for delivering clean images to the Computer Vision models. 

## **4. Conclusion** 

The development and integration of the GEMA architecture demonstrated that largescale auditing of historical web archives requires robustness across all three pipeline phases: intelligent decentralised collection (via modality-agnostic crawlers on Arquivo.pt/MongoDB), context-aware layout cleaning (Trafilatura), and scalable multimodal processing (YOLO + NER/Census). 

By replacing brittle, rule-based HTML approaches and temporary local files with modular, fault-tolerant extractors, the pipeline consolidated itself as a reliable mechanism for longitudinal research. The semantic complexity ladder proved critical for navigating sports-specific language, ensuring that the final dataset accurately exposes asymmetries in athlete visibility. The resulting infrastructure fully meets the persistence and analytical quality requirements for the projected web demonstrator, while providing the scientific rigour demanded by gender equity studies in national sport. 

