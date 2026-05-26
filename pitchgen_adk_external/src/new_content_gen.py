import concurrent.futures
import re

from google import genai
from google.cloud import discoveryengine
from google.cloud import secretmanager
from google.genai import types
from google.genai.types import GenerateContentConfig
from src.configuration import configuration


def search_vertex_datastore(
    project_id, location, datastore_id, query, num_results=3
):
  from google.api_core.client_options import ClientOptions

  endpoint = (
      f"{location}-discoveryengine.googleapis.com"
      if location and location != "global"
      else "global-discoveryengine.googleapis.com"
  )
  client_options = ClientOptions(api_endpoint=endpoint)
  client = discoveryengine.SearchServiceClient(client_options=client_options)
  serving_config = client.serving_config_path(
      project=project_id,
      location=location,
      data_store=datastore_id,
      serving_config="default_config",
  )
  request = discoveryengine.SearchRequest(
      serving_config=serving_config,
      query=query,
      page_size=num_results,
      content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
          extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
              max_extractive_answer_count=3
          )
      ),
  )

  try:
    response = client.search(request)
    results = []
    for result in response.results:
      content = ""
      extractive_answers = result.document.derived_struct_data.get(
          "extractive_answers", []
      )
      if extractive_answers:
        content = " ".join(
            [ans.get("content", "") for ans in extractive_answers]
        )
      else:
        struct_data = result.document.struct_data
        if struct_data:
          content = str(struct_data)

      url = ""
      if "link" in result.document.derived_struct_data:
        url = result.document.derived_struct_data["link"]
      elif (
          hasattr(result.document, "content")
          and result.document.content
          and result.document.content.uri
      ):
        url = result.document.content.uri

      doc_dict = {
          "page_content": content,
          "metadata": {"url": url, "name": datastore_id},
      }
      results.append(doc_dict)
    return results
  except Exception as e:
    print(f"Error searching datastore {datastore_id}: {e}")
    return []


class CustomEnsembleRetriever:

  def __init__(self, url_list):
    self.config = configuration()
    self.project_id = self.config["default"]["PROJECT_NAME"]
    self.location = self.config.get(
        "default",
        "discovery_engine_location",
        fallback=self.config.get("default", "region", fallback="global"),
    )

    self.client = genai.Client(
        vertexai=True,
        project=self.project_id,
        location=self.config["default"]["region"],
    )

    from src.new_content_gen import get_datastoreID

    self.pitch_decks_ds_id = get_datastoreID("pitch_decks")
    self.website_ds_id = get_datastoreID("website")

  def retrieve(self, query):
    results = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
      futures = [
          executor.submit(
              search_vertex_datastore,
              self.project_id,
              self.location,
              self.pitch_decks_ds_id,
              query,
          ),
          executor.submit(
              search_vertex_datastore,
              self.project_id,
              self.location,
              self.website_ds_id,
              query,
          ),
      ]

      for future in concurrent.futures.as_completed(futures):
        try:
          res = future.result()
          if res:
            results.extend(res)
        except Exception as e:
          print(f"Error in ensemble search: {e}")
    return results

  def batch(self, queries):
    return [self.retrieve(q) for q in queries]


def ensemble_retriver(url_list):
  return CustomEnsembleRetriever(url_list)


def get_datastoreID(datastoreName):
  config = configuration()
  try:
    sec_client = secretmanager.SecretManagerServiceClient()
    sec_parent = sec_client.secret_path(
        project=config["default"]["PROJECT_NAME"],
        secret=config["datastore"][datastoreName],
    )
    response = sec_client.access_secret_version(
        request={"name": f"{sec_parent}/versions/latest"}
    )
    return response.payload.data.decode("UTF-8")
  except Exception as e:
    print(
        f"Could not access secret for {datastoreName}, falling back to"
        f" default: {e}"
    )
    return config["datastore"][datastoreName]


def generate_cust_info(customer_name, context):
  config = configuration()
  project_id = config["default"]["PROJECT_NAME"]
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location=config["default"]["region"],
  )
  number_of_slides = 6
  msg1_text1 = types.Part.from_text(
      text=f"""You will be provided with a customer name, context and number of slides. Use this following information to create slides.

Follow these steps:

1.  Use the provided customer name and context to gather relevant customer information data.
2.  Generate the specified number of slides, ensuring that each slide contains only customer information data.
3.  Organize the customer information data into a clear and concise format on each slide.
4.  Ensure that the content on each slide is accurate and relevant to the customer.
5.  Present the slides in a logical order, ensuring a smooth flow of information.
6.  Review the generated slides to ensure they meet the requirements and are free of errors.
7.  Use the following format for each slide:
    Slide Title: [Slide Title]
    Slide Content: [Slide Content]

<input>
customer name: Shopify Inc
context: Generate Customer Information and swot analysis slide contents for the customer: Shopify Inc with Telecommunications industry showcasing ['Artificial intelligence'] solutionsand using the products of ['Gemini', 'Vertex AI', 'Vertex AI Search for commerce'], with respect to the User's request: "Generate a deck for the customer Shopify on how Google Cloud AI can help improve their business, driving growth and operational productivity."
number of slides: 6
</input>

<output>
**Slide Title: Shopify at a Glance: Empowering Global Commerce**

**Slide Content:**
*   **Company Overview:** Shopify Inc. is a Canadian multinational e-commerce company that provides essential internet infrastructure for commerce. It offers a proprietary platform with a suite of tools for businesses of any size to start, manage, market, and scale their retail operations.
*   **Massive Merchant Base:** As of 2025, Shopify powers over 4.8 million active stores globally, serving merchants in over 175 countries. The platform is a go-to choice for startups and major brands alike, including Tesla, PepsiCo, and Red Bull.
*   **Impressive Scale & Reach:**
    *   **Gross Merchandise Volume (GMV):** Shopify processed a record $292.3 billion in GMV in 2024.
    *   **Q1 2025 GMV:** Reached $74.8 billion, a 23% increase year-over-year.
    *   **Q1 2025 Revenue:** Generated $1.9 billion, marking a 23% year-over-year growth.
    *   **Global Consumers:** Over 875 million consumers worldwide made purchases from Shopify-powered merchants in 2024.
*   **Market Position:** Shopify holds a dominant 30% share of the e-commerce market in the United States.


**Slide Title: Strategic Priorities & Aggressive AI Adoption**

**Slide Content:**
*   **Core Mission:** Shopify's primary goal is to simplify commerce complexity, allowing merchants to focus on their customers and products. The company aims to ship products and features faster than anyone else in the industry.
*   **AI-First Mandate:** CEO Tobi Lütke has established a clear "AI-first" strategy, making AI proficiency a baseline expectation for all employees. Before requesting more resources or staff, teams must demonstrate why a task cannot be accomplished using AI.
*   **Growth Levers:**
    *   **International Expansion:** A key focus is growing its footprint outside of North America, which currently accounts for 65% of GMV.
    *   **Monetization & Take Rate:** The company is continuously expanding value-added services like Shop Pay, merchant cash advances, and fraud prevention to increase its take rate (the share of GMV it captures as revenue).
    *   **Enterprise Focus:** Shopify is increasingly catering to larger businesses with its Shopify Plus offering, which now serves over 52,000 stores.
*   **Internal AI Integration:** AI is being embedded into all facets of the company, from daily workflows to performance reviews, reshaping Shopify's operational DNA.


**Slide Title: Current AI Capabilities: The Shopify Magic Suite**

**Slide Content:**
*   **Shopify Magic Overview:** Shopify offers a suite of free, integrated AI-powered features designed to help merchants start, run, and grow their businesses more efficiently. These tools automate repetitive and time-consuming processes across store building, marketing, and operations.
*   **Key AI-Powered Tools:**
    *   **Sidekick:** A conversational AI assistant that acts as a 24/7 Shopify expert. Merchants can use simple commands to manage inventory, create discounts, analyze sales data for insights, and generate marketing content.
    *   **Content & Text Generation:** Shopify Magic can instantly draft content for product descriptions, email subject lines, blog posts, and ad copy, helping to speed up the writing process and overcome creative blocks.
    *   **Media Generation:** An AI-enabled image editing tool allows merchants to instantly generate, match, or remove backgrounds from product photos with just a few clicks.
    *   **Personalized Customer Interactions:** AI is used to generate quick, personalized responses in live chats via Shopify Inbox and to create personalized product recommendations based on customer data.


**Slide Title: A Strategic SWOT Analysis for Shopify**

**Slide Content:**
*   **Strengths:**
    *   **Dominant Market Position:** A leading e-commerce platform with a massive, loyal merchant base and strong brand recognition.
    *   **User-Friendly Platform:** An intuitive and easy-to-use interface that lowers the barrier to entry for entrepreneurs.
    *   **Robust Partner Ecosystem:** A vast app store with over 10,000 apps and a large network of developer and agency partners extends platform functionality.
    *   **Scalability:** Offers solutions for businesses of all sizes, from startups to large enterprises with Shopify Plus.

*   **Weaknesses:**
    *   **Dependence on a Single Platform:** Focusing exclusively on the Shopify ecosystem may limit appeal to businesses that prefer other solutions like WooCommerce or Magento.
    *   **Investment in R&D:** A perceived need to increase investment in R&D and new technologies to maintain a competitive edge.
    *   **Revenue Model:** A significant portion of revenue is tied to merchant solutions and GMV, which can be vulnerable to economic downturns affecting consumer spending.

*   **Opportunities:**
    *   **AI-Driven Growth:** Aggressively integrating AI can unlock new efficiencies for merchants, enhance personalization at scale, and create a significant competitive advantage.
    *   **International Expansion:** Huge potential for growth in markets outside of North America.
    *   **Enterprise Market:** Continued expansion into the high-volume enterprise segment with Shopify Plus and Commerce Components.
    *   **Financial Services:** Growing its suite of financial products (Shop Pay, Shopify Capital) to deepen merchant relationships and increase monetization.

*   **Threats:**
    *   **Intense Competition:** Faces strong competition from other e-commerce platforms like WooCommerce, BigCommerce, and enterprise solutions from Adobe and Salesforce.
    *   **Economic Headwinds:** A prolonged economic downturn could reduce consumer spending, directly impacting Shopify's GMV-dependent revenue.
    *   **Cybersecurity Risks:** As a platform handling vast amounts of sensitive merchant and customer data, it is a target for data breaches and other cyber threats.
    *   **Changing Technology:** The e-commerce landscape is constantly evolving, requiring continuous investment and adaptation to stay ahead of new tools and platforms.


**Slide Title: Identified Challenges & Key Opportunities**

**Slide Content:**
*   **Challenges:**
    *   **Maintaining Competitive Edge:** The e-commerce platform market is highly competitive, requiring continuous innovation to differentiate from rivals like WooCommerce, BigCommerce, and Amazon.
    *   **Scaling Merchant Success:** As the number of merchants grows, a key challenge is providing scalable tools and support to help millions of individual businesses succeed and grow.
    *   **Economic Sensitivity:** Revenue is closely tied to the success of its merchants and overall consumer spending, making it susceptible to economic slowdowns.
    *   **Technological Advancement:** The rapid pace of technological change, especially in AI, requires constant adaptation and investment to prevent the platform from becoming obsolete.

*   **Opportunities for Growth with Google Cloud AI:**
    *   **Enhance AI Sidekick:** Augment the Shopify Sidekick assistant with Google's powerful **Gemini** models for more advanced reasoning, deeper business insights, and more sophisticated task automation.
    *   **Hyper-Personalization at Scale:** Utilize **Vertex AI** to build and deploy advanced machine learning models that can deliver hyper-personalized product recommendations, marketing campaigns, and user experiences across millions of stores.
    *   **Revolutionize Product Discovery:** Integrate **Vertex AI Search for commerce** to provide merchants with best-in-class, AI-powered search capabilities that understand user intent, leading to higher conversion rates and improved customer satisfaction.
    *   **Streamline Operations:** Leverage Google Cloud's AI to optimize back-end operations, from fraud detection and supply chain logistics to predicting customer behavior and cohort analysis, thereby increasing productivity for both Shopify and its merchants.


**Slide Title: Key Leadership at Shopify**

**Slide Content:**
*   **Tobias "Tobi" Lütke:** Founder & Chief Executive Officer. The visionary leader driving Shopify's strategic direction and its aggressive "AI-first" mandate.
*   **Harley Finkelstein:** President. Focuses on the company's commercial growth, strategic partnerships, and scaling the business globally.
*   **Kaz Nejatian:** Chief Operating Officer & VP, Product. Plays a crucial role in overseeing the company's product strategy and operational efficiency, ensuring Shopify ships impactful products quickly.
*   **Jeff Hoffmeister:** Chief Financial Officer. Responsible for overseeing the company's financial strategy and ensuring its fiscal health to support long-term growth initiatives.
*   **Mikhail Parakhin:** Chief Technology Officer. A key leader in charge of the company's technology strategy and development.
*   **Glen Coates:** VP, Product. Leads product development and strategy, directly influencing the features and tools available to merchants.


</output>

<input>
customer name: JP Morgan Chase
context: Generate Customer Information and swot analysis slide contents for the customer: JP Morgan Chase with Financial Services & Insurance industry showcasing ['Artificial intelligence'] solutionsand using the products of ['Agentspace'], with respect to the User's request: "Generate contents on how Agentspace can help JP Morgan Chase in Financial Services Industry with its extensive knowledge, solutions and AI tools to streamline operations, Increase technological capabilities, driving AI Transformation and provide personalized experiences."
number of slides: 5
</input>

<output>
**Slide Title: JP Morgan Chase at a Glance: A Global Financial Titan**

**Slide Content:**
*   **Company Overview:** JPMorgan Chase & Co. is a leading global financial services firm and the largest bank in the United States by assets. With a history dating back to 1799, the firm is a leader in investment banking, financial services for consumers and small businesses, commercial banking, financial transaction processing, and asset management.
*   **Massive Scale & Reach:**
    *   **Total Assets:** Over $4.6 trillion as of June 2025.
    *   **Assets Under Management (AUM):** Over $4.1 trillion as of March 2025.
    *   **Global Presence:** Operations in more than 60 countries, serving millions of consumers, small businesses, and many of the world's most prominent corporate, institutional, and government clients.
    *   **Workforce:** Employs over 317,000 people worldwide.
*   **Market Leadership:** Recognized as the world's largest bank by market capitalization as of 2024 and ranked #1 on the Forbes Global 2000 list in 2025.


**Slide Title: Financial Performance & Key Business Segments**

**Slide Content:**
*   **Robust Financials:** For the first quarter of 2025, the firm reported a net income of $14.6 billion with managed revenue of $46 billion, an 8% increase year-over-year, surpassing analyst expectations.
*   **Primary Business Segments (by 2023 Revenue):**
    *   **Consumer & Community Banking (CCB):** The largest segment, providing services to over 80 million individuals and businesses through the Chase brand. It generated $70.15 billion in revenue.
    *   **Corporate & Investment Bank (CIB):** A global leader in investment banking, markets, and securities services, generating $48.81 billion in revenue.
    *   **Asset & Wealth Management (AWM):** Manages over $4.1 trillion in assets for institutions, high-net-worth individuals, and retail investors, with $19.83 billion in revenue.
    *   **Commercial Banking (CB):** Serves corporations, municipalities, financial institutions, and non-profits, generating $15.55 billion in revenue.


**Slide Title: Strategic Priorities: Dominance Through Technology and AI**

**Slide Content:**
*   **Massive Technology Investment:** JPMorgan Chase plans to spend approximately $18 billion on technology in 2025, with a strong emphasis on leveraging AI to boost operational efficiency and support business growth.
*   **AI as a Transformative Force:** CEO Jamie Dimon has likened the potential impact of AI to major historical inventions like the steam engine and the internet, convinced its consequences will be "extraordinary."
*   **Deep AI Integration:** The firm has identified over 400 use cases for AI in production across marketing, fraud, and risk management. It employs more than 2,000 AI experts and data scientists and is actively exploring generative AI to enhance software engineering, customer service, and employee productivity.
*   **Pioneering AI Research:** JPMC has a dedicated AI Research program to advance cutting-edge machine learning and related fields. Initiatives include an Explainable AI Center of Excellence and the development of proprietary tools like the "LLM Suite," a ChatGPT-like product being rolled out internally.


**Slide Title: A Strategic SWOT Analysis for JP Morgan Chase**

**Slide Content:**
*   **Strengths:**
    *   **Dominant Market Leadership:** The largest U.S. bank with a massive asset base and strong global brand recognition.
    *   **Diversified Business Model:** Comprehensive services across consumer, corporate, investment, and wealth management segments provide resilient and varied revenue streams.
    *   **Massive Investment in Technology:** An annual technology budget of around $18 billion creates a significant competitive advantage in innovation and efficiency.
    *   **Robust Financial Performance:** Consistently strong revenue and profitability, demonstrating operational excellence.

*   **Weaknesses:**
    *   **Regulatory Scrutiny and Compliance Costs:** As a systemically important bank, it faces complex regulations and high compliance costs, which amounted to $12.3 billion in 2023.
    *   **Operational Complexity:** The sheer size and global scale of operations can create challenges in management and agility.

*   **Opportunities:**
    *   **AI-Powered Transformation:** Aggressively deploying AI can unlock immense value by personalizing customer experiences, streamlining operations, and enhancing risk management.
    *   **Expanding Digital Banking:** The continued shift to digital and mobile platforms presents opportunities to grow its 48.3 million user base and enhance customer engagement.
    *   **Wealth Management Growth:** Leveraging its brand and technology to capture a larger share of the growing wealth management market.

*   **Threats:**
    *   **Intense Competition:** Faces pressure from other major banks, financial service providers, and agile fintech disruptors.
    *   **Geopolitical and Economic Instability:** Global operations are exposed to geopolitical tensions, trade uncertainties, and economic downturns.
    *   **Cybersecurity Risks:** The firm is a prime target for cyberattacks, requiring continuous and significant investment in security infrastructure.


**Slide Title: Challenges & AI-Driven Opportunities**

**Slide Content:**
*   **Key Challenges:**
    *   **Maintaining Efficiency at Scale:** As the bank continues to grow, there is an intense focus on running a lean organization and improving productivity to manage an expense base of ~$95 billion.
    *   **Navigating Regulatory Complexity:** The high cost and complexity of global regulatory compliance remains a significant operational burden.
    *   **Competitive Disruption:** The financial services industry is being reshaped by innovative fintech firms that threaten traditional banking models.
    *   **Economic Headwinds:** Faces uncertainty from potential interest rate changes, trade tensions, and geopolitical risks that can impact all lines of business.

*   **Opportunities for AI Transformation with AgentSpace:**
    *   **Streamline Operations:** Deploy AI agents to automate and augment complex workflows in compliance, fraud detection, and back-office processes, directly addressing the challenge of managing costs and improving efficiency.
    *   **Increase Technological Capabilities:** Empower the firm's 63,000 technologists and 2,000+ AI specialists with advanced tools to accelerate the development and deployment of the 400+ identified AI use cases.
    *   **Drive AI Transformation:** Provide a robust platform to scale generative AI solutions like the internal "LLM Suite" across the enterprise, ensuring that every employee is augmented by AI, fulfilling a key strategic goal set by the CEO.
    *   **Provide Personalized Experiences:** Utilize AI agents to deliver hyper-personalized insights and service to millions of consumer and wealth management clients, strengthening relationships and driving growth.


</output>

<input>
customer name: PepsiCo Inc
context: Generate Customer Information and swot analysis slide contents for the customer: PepsiCo Inc with Consumer Packaged Goods industry showcasing ['Artificial intelligence'] solutionsand using the products of ['Gemini', 'Vertex AI'], with respect to the User's request: "Generate a pitch deck on how Google Cloud can support Pepsico to re-imagine new product innovation and marketing workflows with AI. Also provide the relevant customer references."
number of slides: 5
</input>

<output>
**Slide Title: PepsiCo at a Glance: A Global Food and Beverage Giant**

**Slide Content:**
*   **Company Overview:** PepsiCo, Inc. is a US-based multinational food, snack, and beverage corporation formed in 1965 through the merger of Pepsi-Cola and Frito-Lay. Its portfolio includes some of the world's most recognized brands, such as Lay's, Doritos, Cheetos, Gatorade, Pepsi-Cola, Mountain Dew, and Quaker.
*   **Immense Global Reach:** PepsiCo's products are enjoyed by consumers over a billion times a day in more than 200 countries and territories. The company employs approximately 318,000 people globally.
*   **Market Position:** It is the second-largest food and beverage business in the world, behind Nestlé, and a leader in the global savory snacks market. The company holds 23 brands that each generate more than $1 billion in annual retail sales.
*   **Scale and Financials:** PepsiCo generated nearly $92 billion in net revenue in 2024. The business is almost evenly split between snacks (55%) and beverages (45%).


**Slide Title: Financial Performance & Business Segments**

**Slide Content:**
*   **Full-Year 2024 Performance:**
    *   **Net Revenue:** $91.85 billion, a 0.4% increase year-over-year.
    *   **Net Income:** $9.58 billion, a 6% increase from 2023.
    *   **Resilience:** The company demonstrated resilience despite challenges in North America and geopolitical tensions in some international markets.
*   **First-Quarter 2025 Results:**
    *   **Net Revenue:** $17.9 billion, showing a slight decline.
    *   **Operating Profit:** $2.58 billion.
    *   **Outlook:** The company anticipates low-single-digit organic revenue growth for 2025, citing subdued consumer conditions and higher supply chain costs.
*   **Key Business Segments (by 2024 Operating Profit):**
    *   **Frito-Lay North America (FLNA):** 43%
    *   **PepsiCo Beverages North America (PBNA):** 15%
    *   **Latin America:** 15%
    *   **Europe:** 14%
    *   **Other segments** including Quaker Foods, AMESA, and APAC make up the remainder.


**Slide Title: Strategic Priorities: AI-Driven Innovation & Sustainability**

**Slide Content:**
*   **Winning with pep+:** PepsiCo's core strategy is "pep+" (PepsiCo Positive), a fundamental transformation that places sustainability and human capital at the center of its growth. This includes goals for Net-Zero emissions by 2040 and reducing virgin plastic use.
*   **Aggressive AI & Digital Transformation:**
    *   CEO Ramon Laguarta has prioritized a "much more aggressive" data and AI strategy since 2024.
    *   The company is deploying AI across its entire value chain—from farming and manufacturing to marketing and sales—to enhance market dominance.
    *   A key focus is on enterprise-wide generative AI capabilities, supported by an internal platform called **PepGenX** which allows employees to experiment with Gen AI tools.
*   **Accelerating Product Innovation:**
    *   PepsiCo is using AI to dramatically shorten product development cycles from over six months to just six weeks. AI tools analyze millions of data points from social media, recipes, and menus to identify emerging consumer trends, leading to rapid development of new products like "Off The Eaten Path" seaweed snacks.
    *   The company is actively shifting its portfolio towards healthier options in response to consumer demand.


**Slide Title: A Strategic SWOT Analysis for PepsiCo Inc**

**Slide Content:**
*   **Strengths:**
    *   **Highly Diversified Portfolio:** With 23 billion-dollar brands across snacks and beverages, PepsiCo is less vulnerable to market shifts in a single category.
    *   **Strong Global Brand Recognition:** An immense presence in over 200 countries provides a significant competitive advantage.
    *   **Robust Distribution Network:** A world-class supply chain and distribution network ensures wide product availability.
    *   **Financial Strength:** Consistent profitability allows for significant reinvestment in innovation, marketing, and strategic acquisitions like Poppi.

*   **Weaknesses:**
    *   **Health Perception:** The brand is still heavily associated with sugary, high-calorie products, which is a vulnerability as consumer preferences shift toward wellness.
    *   **Dependence on Carbonated Drinks:** A significant portion of beverage revenue comes from carbonated soft drinks, a category experiencing a global decline.
    *   **Reliance on North American Market:** Over 60% of revenue comes from North America, exposing the company to regional economic and consumer trend shifts.

*   **Opportunities:**
    *   **AI-Powered Innovation and Marketing:** Leveraging **Gemini** and **Vertex AI** can dramatically accelerate the identification of consumer trends, speed up product formulation, and create hyper-personalized marketing campaigns.
    *   **Expansion in Health & Wellness:** Growing consumer demand for healthier, functional, and plant-based products presents a massive market opportunity.
    *   **Growth in Emerging Markets:** There is a vast opportunity to expand in geographies covering 95% of the global population outside of its core markets.

*   **Threats:**
    *   **Intense Competition:** Faces fierce competition from global giants like Coca-Cola, Nestlé, and Unilever.
    *   **Changing Consumer Preferences:** Rapidly shifting tastes and a move away from traditional snack and soda products require constant adaptation.
    *   **Regulatory Pressures:** Increased regulation, such as "soda taxes" and sustainability mandates, could impact costs and sales.


**Slide Title: Challenges and Opportunities with Google AI**

**Slide Content:**
*   **Key Challenges:**
    *   **Rapidly Changing Consumer Tastes:** Staying ahead of fast-moving health, wellness, and flavor trends is a constant challenge that requires deep, real-time consumer understanding.
    *   **Long Innovation Cycles:** Traditionally, bringing a new product from concept to a store shelf could take up to three years, a timeline that is too slow for today's dynamic market.
    *   **Marketing Efficiency at Scale:** Creating resonant and personalized marketing for dozens of brands across hundreds of markets is increasingly complex and expensive.
    *   **Data Integration:** Pulling together massive structured and unstructured datasets from market trends, consumer feedback, and R&D formulas to derive actionable insights is a major hurdle.

*   **Opportunities to Reimagine with Google Cloud AI:**
    *   **Re-imagine Product Innovation with Vertex AI:** Use **Vertex AI** to analyze vast datasets of consumer trends, ingredient interactions, and sensory data. This can help R&D teams rapidly formulate and test new products—from healthier snacks to novel beverage flavors—slashing development time from months to weeks.
    *   **Accelerate Marketing with Gemini:** Leverage **Gemini's** multimodal and advanced reasoning capabilities to analyze social media trends, video, and text to instantly identify micro-trends. Empower marketing teams to generate creative briefs, draft campaign copy, and produce ad visuals, personalizing content for millions of consumers at scale.
    *   **Create a Unified "Innovation Engine":** Integrate **Vertex AI** as the foundation for PepsiCo's PepGenX platform. This can create a seamless workflow from consumer insight to product brief to marketing launch, breaking down silos between R&D, design, and marketing teams for unprecedented speed and agility.

    
</output>

<input>
customer name: Krafton Inc
context: Generate Customer Information slide contents for the customer: Krafton Inc with Gaming industry showcasing ['Artificial intelligence'] solutionsand using the products of ['Gemini', 'Vertex AI', 'Imagen'], with respect to the User's request: "Generate a deck on how Google Cloud's GenAI solutions boost the gaming industry for Krafton."
number of slides: 4
</input>

<output>
**Slide Title: Krafton at a Glance: The Global Powerhouse Behind PUBG**

**Slide Content:**
*   **Company Overview:** Krafton, Inc. is a premier South Korean video game publisher and holding company. It operates a federation of independent global studios, including PUBG STUDIOS, Bluehole Studio, and Striking Distance Studios, to create unique and engaging gaming experiences.
*   **Flagship IP:** The company is globally renowned for *PUBG: BATTLEGROUNDS*, a cultural phenomenon that has sold over 75 million copies and established the Battle Royale genre.
*   **Global Reach & Scale:** Krafton's products are enjoyed by a massive player base in over 200 countries. The company is headquartered in Seoul, South Korea, with a significant presence in Asia, the Americas, and Europe.
*   **Key Titles:** The portfolio includes major hits like *PUBG: BATTLEGROUNDS*, *BATTLEGROUNDS MOBILE INDIA (BGMI)*, *The Callisto Protocol*, and the upcoming life simulation game *inZOI*.


**Slide Title: Record-Breaking Financials & Platform Dominance**

**Slide Content:**
*   **Record H1 2025 Performance:** Krafton achieved its best-ever first-half performance, reporting a record-breaking revenue of ₩1.54 trillion (approx. $1.1 billion) and an operating profit of ₩703.3 billion (approx. $505 million). This represents an 11.9% increase in revenue and a 9.5% rise in operating profit year-over-year.
*   **Revenue by Platform (H1 2025):**
    *   **Mobile:** ₩960 billion ($690 million), accounting for the lion's share of revenue.
    *   **PC:** ₩543.2 billion ($390 million), showing strong growth driven by live service updates.
    *   **Console:** ₩33 billion ($23 million).
*   **Growth Drivers:** The continued global success of the *PUBG* franchise, particularly on PC, and the strategic growth of *BATTLEGROUNDS MOBILE INDIA (BGMI)* in the Indian market are key revenue drivers.


**Slide Title: Strategic Vision: "Scale-up the Creative" with an AI Focus**

**Slide Content:**
*   **Core Strategy: "Scale-up the Creative":** Krafton's primary strategy is to discover and nurture unique creative ideas and scale them into globally beloved and enduring IPs. This involves operating over 20 development pipelines for new titles.
*   **Expanding the PUBG Universe:** A core pillar of the strategy is to franchise the *PUBG* IP, expanding it with new titles like the upcoming extraction shooter *Project Black Budget* and transforming it into a broader gameplay platform.
*   **Aggressive Investment in New IPs & AI:**
    *   The company is actively investing in new franchises like *inZOI* and *Subnautica 2* and has acquired multiple studios to diversify its portfolio.
    *   Krafton is heavily investing in AI and deep learning to introduce new forms of gameplay, improve production efficiency, and create new ways to generate content.
*   **Future Growth Ambition:** The company has set an ambitious target to achieve an annual revenue of 7 trillion won by 2029, driven by both the *PUBG* IP and a pipeline of new blockbuster games.


**Slide Title: Challenges & Opportunities for GenAI Transformation**

**Slide Content:**
*   **Key Challenges:**
    *   **High Development Costs & Timelines:** Creating high-fidelity, AAA game worlds and content is resource-intensive and time-consuming, posing a risk to innovation.
    *   **Sustaining Live Service Engagement:** Keeping millions of players engaged in evergreen titles like *PUBG* requires a constant stream of fresh, high-quality content and updates.
    *   **IP Diversification Risk:** While a strategic priority, developing new blockbuster IPs to reduce dependency on *PUBG* is inherently challenging and capital-intensive.
    *   **Scaling Creativity:** Fostering and scaling unique creative ideas across a growing portfolio of over 20 game pipelines presents a significant operational challenge.

*   **Opportunities with Google Cloud GenAI:**
    *   **Accelerate World-Building with Imagen:** Rapidly generate concept art, environmental assets, and unique textures, empowering artists to visualize and build vast, immersive game worlds like those in *Project Windless* or *Subnautica 2* faster than ever.
    *   **Create Dynamic Content with Gemini:** Use advanced reasoning to generate branching narratives, dynamic NPC dialogue, and unique questlines in real-time, fulfilling the vision of creating new forms of gameplay and enhancing player retention in live services.
    *   **Streamline Production with Vertex AI:** Build custom AI models on the **Vertex AI** platform to automate asset creation, code generation, and quality assurance testing, directly addressing the goal of improving production efficiency and allowing developers to focus on creativity.

    
</output>

<input>
customer name: {customer_name}
context: {context}
number of slides: {number_of_slides}
</input>

<output>"""
  )
  si_text1 = """You are a content generation specialist. Your task is to generate a specific number of slides with only the customer information data for a given customer based on the provided customer name and context."""

  model = config["default"]["GEMINI_MODEL"]
  contents = [
      types.Content(role="user", parts=[msg1_text1]),
  ]
  tools = [
      types.Tool(google_search=types.GoogleSearch()),
  ]

  generate_content_config = types.GenerateContentConfig(
      temperature=1,
      top_p=0.95,
      seed=0,
      max_output_tokens=65535,
      safety_settings=[
          types.SafetySetting(
              category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
          ),
      ],
      tools=tools,
      system_instruction=[types.Part.from_text(text=si_text1)],
  )
  text_chunks = []
  for chunk in client.models.generate_content_stream(
      model=model,
      contents=contents,
      config=generate_content_config,
  ):
    if not chunk.candidates or not chunk.candidates[0]:
      continue
    content = chunk.candidates[0].content
    if not content or not content.parts:
      continue

    for part in content.parts:
      if hasattr(part, "text") and part.text:
        text_chunks.append(part.text)

  final_response = "".join(text_chunks)

  return final_response


#   text_chunks=[]
#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
#         continue
#     #print(chunk.text, end="")
#     text_chunks.append(chunk.text)

#   final_response = "".join(text_chunks)
#   #print(type(final_response))

#   return final_response


def generate_questions(agenda):
  config = configuration()
  project_id = config["default"]["PROJECT_NAME"]
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location=config["default"]["region"],
  )

  msg1_text1 = types.Part.from_text(
      text=f"""You will be provided with an agenda. Your task is to generate not more than 3 questions based on the agenda.

Here is the agenda:
{agenda}

Instructions:

1.  Analyze the provided agenda to identify key topics and objectives.
2.  Generate not more than 3 questions that are relevant to the agenda's content.
3.  Ensure the question is clear, concise, and open-ended to encourage discussion.
4.  Focus on questions that explore different aspects of the agenda items."""
  )
  si_text1 = """You are an AI assistant designed to generate question based on a given agenda. Your goal is to create insightful and relevant question that facilitate discussion and exploration of the topics outlined in the agenda."""

  model = config["default"]["GEMINI_MODEL"]
  contents = [
      types.Content(role="user", parts=[msg1_text1]),
  ]

  generate_content_config = types.GenerateContentConfig(
      temperature=1,
      top_p=1,
      seed=0,
      max_output_tokens=65535,
      safety_settings=[
          types.SafetySetting(
              category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
          ),
      ],
      system_instruction=[types.Part.from_text(text=si_text1)],
  )
  text_chunks = []
  for chunk in client.models.generate_content_stream(
      model=model,
      contents=contents,
      config=generate_content_config,
  ):
    if not chunk.candidates or not chunk.candidates[0]:
      continue
    content = chunk.candidates[0].content
    if not content or not content.parts:
      continue

    for part in content.parts:
      if hasattr(part, "text") and part.text:
        text_chunks.append(part.text)

  final_response = "".join(text_chunks)

  return final_response


#   text_chunks=[]
#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     #print(chunk, end="")
#     #print(chunk.text, end="")
#     text_chunks.append(chunk.text)

#   final_response = "".join(text_chunks)
#   #print("final_response: ",final_response)

#   return final_response


def generate_contents(all_content_string, agenda, number_of_slides):
  config = configuration()
  project_id = config["default"]["PROJECT_NAME"]
  client = genai.Client(
      vertexai=True,
      project=project_id,
      location=config["default"]["region"],
  )

  msg1_text1 = types.Part.from_text(
      text=f"""You will be provided with a large text, an agenda and the number of slides to be generated per each agenda. Use the information from the large text to create slides for the given agenda.

Follow these instructions:
1. Analyze the large text and identify the key points relevant to the agenda.
2. Create a maximum of {number_of_slides} slides for each agenda item.
3. Each slide should have a title and content.
4. The slide title should be concise and descriptive.
5. The slide content should be brief and to the point, summarizing the key information from the text.
6. Use the following format for each slide:
   Slide Title: [Slide Title]
   Slide Content: [Slide Content]

<input>
Large Text: But legacy data solutions struggle to provide actionable, near real-time insights in a scalable and cost-efficient manner Increasing data volume &amp; fragmentation Customer, sales, inventory, and operational data are growing but siloed Lack of analytics &amp; AI/ML solutions Legacy data analytics tools are not robust enough to extract rich insights from data Limited actionable insights Teams cannot make timely decisions to meet rising customer expectations For more information: Traditional Data Approach.
With lots of on-premises or legacy systems, data gets siloed, and copied over and over again by users till there are outdated systems in lots of different places. In addition, once datasets start growing larger, data quality can become a problem.
Legacy data solutions struggle to provide actionable, near real-time insights in a scalable and cost-efficient manner Increasing data volume &amp; fragmentation Customer, sales, inventory, and operational data are growing but siloed Lack of analytics &amp; AI/ML solutions Legacy data analytics tools are not robust enough to extract rich insights from data Limited actionable insights Teams cannot make timely decisions to meet rising customer expectations For more information: Traditional Data Approach.
Substantial compliance risk: A lack of strategy usually leads to inadequate governance, increasing the risk of data breach and privacy violations. In the context of AI, building an effective data strategy becomes even more crucial, especially given the excitement around generative AI.
Leveraging this data to deliver a fully cross-channel customer experience is challenging Data silos prevent a holistic view of the customer Data is collected across channels but legacy technology and organizational silos prevent proper analysis Current analysis doesn&#39;t always produce actionable results Existing systems don&#39;t always produce actionable insights and organizational barriers prevent full utilization of current analysis Legacy systems don&#39;t scale or produce actionable models Legacy systems don&#39;t integrate with new platforms or meet the needs for improved marketing performance.
DCAM data and analytics assessment framework CDMC best practice assessment and certification Master Data Management Duplicate Suspect Processing rules Solution and department scope Enterprise Knowledge Graph KG Entity Resolution/reconciliation and Financial Crime Record matching MDM + ML Tamr Cloud-Native Master Data Management Site Reliability Data Pipelines SLA Data at Rest SLA SLAs applied to data pipeline SLAs applied to services managing data DR strategies for data Registering, creating, and scheduling data pipelines is a recurring challenge that organizations face.
Here&#39;s how to build a robust data and AI governance framework: Prioritize data quality to drive ROI Rise above architecture for compliance and efficiency Banish dark, duplicate, and dirty data to maximize ROI Govern AI models in production 66% of organizations have at least half of their data dark, posing significant risk4 4 Recent Google Cloud survey of IT Decision Makers and Influencers from organizations 500+ with AI workload use or interest.
Adopting comprehensive monitoring and services that simplify compliance can help your organization build a more robust and resilient data ecosystem, equipped to adapt quickly while adhering to stringent industry standards and regulatory requirements.
● Build Future-Ready Foundation: Adapt to emerging technologies and market shifts. ● Connect All Factories by 2030. ● Scale Infrastructure ● Simplify MLOps ● Optimize with Multi-Cloud ● Accelerate Tech Adoption ● Ensure Architectural Governance Within 3 Years Within 5 Year.
Set the location for your data by using organization policies so that your data at rest and your resources remain only in that region. Select the key-management option (such as the key rotation period) that best meets your security and compliance requirements.
01 02 03 04 05 Create an AI-first data strategy Connect all your data to AI to drive insights Boost productivity with agents in every data task Ensure data security and governance Improve efficiency to reduce data cost and scale 5 steps for building a data foundation for success at YOUR_COMPANY.
Managing and working with data at scale is hard, and poses a new challenge when compared to working with data in the past; in many cases, this is balanced by today&#39;s better process automation and tools to make sense of the data. Of course, more access means new challenges in security, in quality, and interpretability.
Agility Governance/Control Control where and how data is used Efficiency Build portable, repeatable data processes Collaborate on data model development and iteration Make better decisions based on fresh data Save 70% of analyst time Reduce risk, yet provide self-service access to data Respond quickly to change Simplify and accelerate data pipelines Unify your organization with centralised, auditable business logic Drive organisational agility, efficiency and governance objectives Leverage database technology, support multi-cloud Reduce costs and improve performance.
● Conduct meetings with stakeholders to align on scope and objectives and identify key data and analytics use cases ● Capture high level requirements ● Understand and assess the current environment in relation to capabilities, systems and data ● Identify related projects (current and planned) and determine dependencies ● Review and validate data architecture principles that inform design and prioritisation activities ● Review and validate data capabilities in the Endeavour Business Capability Model ● Review and validate target start data architecture ● Using outside-in thinking, identify any gaps in principles, capabilities and/or target state architecture ● Validate findings with key stakeholders and agree areas requiring further attention and elaboration ● Define approach to govern data asset design, including roles and responsibilities, processes, policies and standards, etc.
By applying governance practices, Endeavour can maximise the value derived from data, minimise risks associated with poor data management and address data-related challenges such as data quality issues, siloed data and compliance breaches.
Enterprise Data Principles The Data Architecture Principles complement Endeavour&#39;s existing Enterprise Data Principles ● Enterprise data principles provide the framework for the EGL data community to manage and use data across the data lifecycle Safe data ensures we meet our legal obligations and are responsible with the use of data, while Trusted data provides internal confidence in the quality of our data ● Data Accountability is key to good privacy and data governance practices Safe Trusted Data Custodianship We will assign data custodianship and stewardship to ensure the management and protection of data across the data lifecycle Responsibility We will collect, store, and use data responsibly in line with our Responsible Use of Data principles Transparency We will be transparent about data collection and use to allow customers and team members to make informed decisions Consent We will respect our customers&#39; and teams&#39; privacy choices Security We will ensure data is secured and protected Strong Protections We will know and meet our legal obligations to best serve our customer Data Integrity &amp; Quality We will ensure data integrity is maintained as data is shared across the organisation, and data quality is continually enhanced from the point of collection Democratise Data We will collaborate and share data appropriately internally and with trusted partners for better customer and team outcomes Robust Practices We will apply analytical rigour to provide trusted insights and avoid unintended consequences Insights Led We will enable the business through fact-based decision making and analytical innovation into our organisational DNA We have established enterprise data principles to foster trust with our customers, enhance personalisation experiences, and increase brand loyalty.
For example, building digital fingerprints of the firm&#39;s data to automatically identify and track it over time, which could enable significant benefits to the firm&#39;s ability to make strategic business decisions and improve its trading flows in the future.
Put simply, if your data isn&#39;t ready for AI, neither is your business. Therefore, a well-defined data strategy that aligns processes, technology, and people is now essential for harnessing your data and transforming it into a strategic asset that powers sustainable value.
● Incorporate tools for data loss prevention, obfuscation, tokenization, encryption and logging can help firms meet the security, privacy and data lineage requirements of emerging data-related regulations and user preferences. 
AI opens up new opportunities to combine structured data with unstructured data, such as emails, PDFs, and social media. Advancements like natural language process (NLP), computer vision, and multimodal gen AI models are transforming our ability to gain previously untapped insights to deliver tangible business value.
Secure, compliant, and resilient infrastructure at global scale World class data + AI/ML capabilities Packaged, repeatable solutions designed to help solve FSI-specific challenges We can address the needs of banks and payment firms at different layers Cloud Infrastructure Foundation 2 Data &amp; AI Platform 1 3 FSI Industry Solutions 
New technologies like cloud computing, predictive analytics, artificial intelligence (AI), and machine learning (ML) are now seen as core business drivers, enabling companies to adapt quickly — especially in unpredictable conditions.
What is Data Center Transformation? An approach to Digital Transformation starting with focus on exiting or greatly consolidating an existing IT estate ● Not just migration of VMs ● Not just Lift and Shift Delivering Four Critical Domains of Enterprise Value: Business, Operational, Technical, and Financial Through a holistic assessment and change strategy focusing on: Partnerships, People and Culture, Applications, Data, Infrastructure, and Security &amp; Resilience Outcome Measures Infrastructure Data and Insight Applications ● Complete data center exit capability ● Solutions for the entire enterprise estate from mainframe to serverless ● Simplify and make data pervasive and accessible ● Drive intelligence with Analytics, AI &amp; ML Partnership ● Establish Partnerships with Alphabet, Google and Ecosystem partners to drive innovation ● Attract talent, Upskill, Reskill and build processes for collaboration and agility like DevSecOps and SRE People and Culture ● Write once run anywhere ● API driven business ● Compliant secure systems, data and Users ● Privately managed network Security &amp; Resilience Business Operational Technical Financial.
Navigate a data center transformation with a partner, not a provider Craft the right data center transformation plan for your business, together Migrate with Google experts, to a more secure cloud Grow confidently on our purpose built infrastructure Modernize at your own pace, using Anthos to bridge the gap between legacy and cloud Vision Insight Experience Understanding Execution Accountability Enablement Mastery Partnership Shared Mission Investment Co-innovation Ecosystem Capability Products Solutions Value Strategy Guidance Expertise Framework Transformational Partnership.
A data platform that supports sophistication Collect Data Transfer Service Pub/Sub Datastream Process Dataproc (Spark, Flink, Presto, MapReduce) Data Fusion Dataflow (Unified Streaming and Batch) Store Activate Relational Databases NoSQL Databases Cloud SQL Spanner Bigtable Firestore SaaS Applications IoT Devices Social Media Dataprep (Wrangling) Corporate and 3rd Systems E-Commerce Geospatial Decision Making App Development SaaS Applications Exception Management Operational Intelligence Data Monetization Analyze BigQuery BI Engine Multi Cloud BQML Data QnA Memorystore Google Storage Composer (Orchestration) Data engineers Clean, useful data Data scientists Models that work Developers Intelligent apps Data analysts Query and analyze Vertex AI Training AutoML Explainable AI Predication Empower Intelligent Data Fabric Enterprise Capabilities App Platforms AppSheet Firebase Business Intelligence Looker APIs Partner and Open Source Technology Connected Sheets Analytics Hub Dataplex Data Catalog IAM CMEK Disaster recovery Zones Network MLOPs ML engineers Integrated intelligence Consumers Value Business users Insights Everywhere AI Solutions CCAI DocAI Retail Search Visual Inspection Database Migration Service.
A cloud strategy can build the resiliency needed to adapt to these trends and accelerate the transformation Bridge the gap between IT and OT to create a digital thread of multi-source data with context and relationships for advanced decision making Capture incremental value via enterprise platforms to deliver services, unlock innovation faster, and open new revenue opportunities while getting closer to end-customers Adopt a digitally enabled anywhere-workforce model and close the talent gap Build a composable distributed technology infrastructure from edge to cloud Maintain highest levels of cybersecurity with advanced tools and dedicated experts 

Agenda: FS Data Management Challenges.

number of slides: 5
</input>

<output>
Slide Title: The Legacy Data Dilemma

Slide Content:
   Increasing Fragmentation: Customer, sales, and operational data are growing rapidly but remain siloed across legacy and on-premises systems.
   Data Duplication & Degradation: Data is copied repeatedly, leading to outdated, dark, duplicate, and dirty data, and a general decline in data quality. 66% of organizations have at least half their data dark.
   Lack of Actionable Insights: Teams struggle to make timely, data-driven decisions because legacy analytics tools are not robust enough to extract rich insights from fragmented data.


Slide Title: Data Silos Prevent a Holistic View

Slide Content:
   Incomplete Customer View: Data collected across multiple channels and organizational silos prevents a proper, holistic analysis of the customer journey, hindering personalization and service.
   Ineffective Analysis: Existing systems and organizational barriers prevent the full utilization of data, meaning analysis often fails to produce actionable results.
   Integration Failures: Legacy systems don't scale or integrate with modern platforms, failing to meet the demands for improved performance and advanced analytical models.


Slide Title: Mounting Governance & Compliance Risks

Slide Content:
   Substantial Compliance Risk: A lack of clear data strategy and governance increases the risk of data breaches, privacy violations, and failure to meet regulatory requirements.
   Poor Data Accountability: Without assigned custodianship and stewardship, it's difficult to manage and protect data across its lifecycle, leading to poor data management.
   Security Challenges at Scale: As data access increases, so do the challenges in security, quality, and interpretability, requiring robust tools for encryption, data loss prevention, and access control.


Slide Title: Barriers to Scalability and Innovation

Slide Content:
   Struggling with Scale: Managing and working with data at today's scale is a significant challenge, and legacy systems lack the capacity to handle modern data volumes effectively.
   Inability to Leverage AI/ML: A poor data foundation is a primary blocker to innovation. If your data isn't ready for AI with proper governance and quality, your business isn't either.
   Hindered Agility: The inability to build portable, repeatable data processes or simplify data pipelines prevents organizations from responding quickly to change and market shifts.


Slide Title: The Strategic Imperative for a Modern Data Foundation

Slide Content:
   Connect All Data to AI: A modern data strategy is essential to connect all your data, drive insights, and transform data into a strategic asset that powers sustainable value.
   Maximize Value, Minimize Risk: Applying strong governance practices allows firms to maximize the value derived from data while minimizing risks associated with poor data management and compliance breaches.
   Build a Future-Ready Foundation: A modern, cloud-based data platform provides the resiliency and agility to adapt to emerging technologies, market shifts, and new business demands.


</output>

<input>
Large Text: Here&#39;s how to build a robust data and AI governance framework: Prioritize data quality to drive ROI Rise above architecture for compliance and efficiency Banish dark, duplicate, and dirty data to maximize ROI Govern AI models in production 66% of organizations have at least half of their data dark, posing significant risk4 4 Recent Google Cloud survey of IT Decision Makers and Influencers from organizations 500+ with AI workload use or interest.
By converting raw data into meaningful metrics using LookML, you empower BI users across the entire enterprise, from accounting to marketing, to easily get started building their dashboards with the confidence that comes from knowing their metrics are properly defined and aggregated.
Optimize Define &amp; Promote KPIs Measure Success Share Success Stories Ensure Value Creation Accelerate &amp; Sustain Change Activate Establish Operating Principles Train &amp; Upskill Members Manage Change Assess Readiness Establish Best Practices Jumpstart Understand &amp; Envision Build Strategy Establish Executive Support Secure Funding Excite Employees Strategize &amp; Design Create Structure Build Team Align Organization Prepare Leaders Build Deployment Plan.
Sigma eliminates BI bottlenecks and inaccurate analyses by establishing a single, reusable, and accessible source of truth for all users to query.
○ Ensure robust data security and privacy through strict access controls, encryption, data masking, and data loss prevention technologies.
It involves ingesting the necessary data into the data warehouse, creating data models in enterprise BI systems like Looker that can join data from 10 to 20 SaaS apps or across public clouds, then having that source of truth accessible and available to teams without provisioning lags or request bottlenecks along the way.
● Conduct meetings with stakeholders to align on scope and objectives and identify key data and analytics use cases ● Capture high level requirements ● Understand and assess the current environment in relation to capabilities, systems and data ● Identify related projects (current and planned) and determine dependencies ● Review and validate data architecture principles that inform design and prioritisation activities ● Review and validate data capabilities in the Endeavour Business Capability Model ● Review and validate target start data architecture ● Using outside-in thinking, identify any gaps in principles, capabilities and/or target state architecture ● Validate findings with key stakeholders and agree areas requiring further attention and elaboration ● Define approach to govern data asset design, including roles and responsibilities, processes, policies and standards, etc.
Architects should be engaged earlier in the process. Data Governance ● Opportunity to define metrics to monitor the adoption of the data governance framework (eg data quality score, aligned vs. misaligned solutions, data catalogue coverage, adoption, etc.).
Agility Governance/Control Control where and how data is used Efficiency Build portable, repeatable data processes Collaborate on data model development and iteration Make better decisions based on fresh data Save 70% of analyst time Reduce risk, yet provide self-service access to data Respond quickly to change Simplify and accelerate data pipelines Unify your organization with centralised, auditable business logic Drive organisational agility, efficiency and governance objectives Leverage database technology, support multi-cloud Reduce costs and improve performance.
There is already significant technical debt. ● The business and product owners are demanding fast time to value. In some cases, this has resulted in standards being compromised. There needs to be a better balance between good design and fast time to value. Architects should be engaged earlier in the process.
The most common form of this I&#39;ve seen is that metrics are defined differently within each tool and there is no centralized data governance, which leads to unnecessarily duplicated workflows across the company. Looker, now part of Google Cloud, can help address these &quot;in-between product&quot; issues.
● Conduct meetings with stakeholders to align on scope and objectives and identify key data and analytics use cases ● Capture high level requirements ● Understand and assess the current environment in relation to capabilities, systems and data ● Identify related projects (current and planned) and determine dependencies ● Review and validate data architecture principles that inform design and prioritisation activities ● Review and validate data capabilities in the Endeavour Business Capability Model ● Review and validate target start data architecture ● Using outside-in thinking, identify any gaps in principles, capabilities and/or target state architecture ● Validate findings with key stakeholders and agree areas requiring further attention and elaboration ● Define approach to govern data asset design, including roles and responsibilities, processes, policies and standards, etc.
Substantial compliance risk: A lack of strategy usually leads to inadequate governance, increasing the risk of data breach and privacy violations. In the context of AI, building an effective data strategy becomes even more crucial, especially given the excitement around generative AI.
Should Have HLR-BI-06 The ability to perform geocoding and visual mapping.
Lak: I believe that data governance does not need to become a burden, a price that you have to pay in order to be able to use data. Instead, data governance is the set of best practices that you implement so that your data becomes trustworthy. Data governance practices contribute positively to data quality.
Solid data governance focussed on data utility We need to strengthen the data foundations Our aim is to create more value with less effort A consistent and easy to use data warehouse Better BI tooling through Looker 2023 priority DA1 DA2 DA2.
How to move the measure? Consider appointing a data ambassador to act as the bridge between the data and business, keeping them both aligned Enable ● Onboards new users on their team with basic Looker training ● Answers questions from team members Evangelize ● Provide inspiration on new ways for team to interact with data in everyday workflows ● Share stories on successful and innovative use cases Collaborate ● Strategize on defining business logic and definitions of KPIs ● Acts as a liaison between the analytics team and the business team.
Don&#39;t take our word for it… Source: McKinsey, HBR, Gartner Companies that treat data like a product can reduce the time it takes to implement new use cases by as much as XX%.” –HBR, “A Better Way to Put Your Data to Work” (2022) .
3. Limited Agility: Analytical platform capacity issues, restricted data access, a locked-in ecosystem, slow QA, and a lack of platform elasticity are key problems.
01 Enhanced Data Governance and Security The bank can leverage its existing GCP-based data governance tools and security measures across the entire analytics pipeline. This ensures consistent data protection, compliance with industry regulations, and centralized control over data access and usage.
● Data Management: data discovery, classification, and management across your data landscape. This includes centralized metadata management, data governance capabilities, and tools to identify and protect sensitive data.
TACTICAL (1.4/5) ● Map Data Initiatives to Measurable Business Outcomes: Prioritize projects that clearly support specific, quantifiable strategic goals. This proves the value of data analytics to business leaders. ● Establish Shared KPIs: Define success metrics jointly between data/AI teams and business units.
By converting raw data into meaningful metrics using LookML, you empower BI users across the entire enterprise, from accounting to marketing, to easily get started building their dashboards with the confidence that comes from knowing their metrics are properly defined and aggregated.
Data-driven Products and Monetization Is your organization effectively able to monetize data to drive business value? TACTICAL (1.4/5) ● Prioritize High-Value Data: Assess your data assets for uniqueness, accuracy, relevance to target audience needs, and sufficient volume to be impactful.
Business users will feel more empowered than ever, while data leaders will be able to preserve the trust and security their organization needs. This combination of ​self-serve and governed BI together will help enterprises make better data-driven decisions.
Data and AI Strategy together leads to scale and enables AI enterprise-wide ABC&#39;S AI STRATEGY 2024 2025 2026 AI Products at Limited Scale Advanced AI Products Scaling Across Business Functions And Geographies Data and AI Strategy Definition Outcomes: Requirements for products, capabilities to develop, scope for AI governance, structure of D&amp;A organization, immediate steps Outcomes: (H1) MVP of AI governance with Responsible AI component, D&amp;A org design (strategy, development, PM and execution control roles) (H2) Learning &amp; training capabilities for cultural shift towards AI, AI product approach, new roles (AI Product owner), AI Accelerator components to speed up AI product delivery Outcomes: Multiple AI products, advanced AI capabilities, bigger cultural shift effort (learning &amp; training capabilities across organization), AI products adoption, AI product structure, AI governance capabilities for risk reduction, D&amp;A &amp; Analytics office reporting model implementation Outcomes: Scale comparable AI products across BUs, advanced platform capabilities *GenAI use cases as AI products.
Through the company&#39;s climate analytics visual platform, Climate Explorer, it provides a dynamic view of risk by applying predictive and generative AI modeling techniques to geospatial data derived from remote sensing and frontier climate science.
● Conduct meetings with stakeholders to align on scope and objectives and identify key data and analytics use cases ● Capture high level requirements ● Understand and assess the current environment in relation to capabilities, systems and data ● Identify related projects (current and planned) and determine dependencies ● Review and validate data architecture principles that inform design and prioritisation activities ● Review and validate data capabilities in the Endeavour Business Capability Model ● Review and validate target start data architecture ● Using outside-in thinking, identify any gaps in principles, capabilities and/or target state architecture ● Validate findings with key stakeholders and agree areas requiring further attention and elaboration ● Define approach to govern data asset design, including roles and responsibilities, processes, policies and standards, etc.
An overview of these platforms is provided below. They are largely SaaS offerings (with the exception of SSRS which is hosted on Langton&#39;s infrastructure). There is a program of work to migrate and combine both Tableau instances onto Endeavour infrastructure with Tableau being identified as the strategic BI platform.
Architects should be engaged earlier in the process. Data Governance ● Opportunity to define metrics to monitor the adoption of the data governance framework (eg data quality score, aligned vs. misaligned solutions, data catalogue coverage, adoption, etc.).
97% 49% &lt;10% Most BI &amp; Analytics “modernization” efforts fail Identify Recognize importance of data &amp; BI applications to their business strategy Prioritize Actively launching new BI &amp; analytics initiatives Transform Reach &quot;transformational&quot; level of maturity in data &amp; analytics.

Agenda: Governance, Analytics & BI.

Number of Slides: 4
</input>

<output>
Slide Title: The Governance, Analytics & BI Challenge

Slide Content:
   High Failure Rate: Most BI & analytics modernization efforts fail, with less than 10% of organizations reaching a transformational level of maturity.
   Inadequate Governance: A lack of strategy leads to inadequate governance, increasing compliance risks, data breaches, and fragmented workflows with inconsistently defined metrics.
   Technical Debt vs. Speed: The business demand for fast time-to-value often leads to compromised standards and accumulating technical debt.
   Limited Agility & Bottlenecks: Analytical platform capacity issues, restricted data access, and slow processes create BI bottlenecks and inaccurate analyses.


Slide Title: Building a Robust Data Governance Framework

Slide Content:
   Principle: Data governance is not a burden but a set of best practices to make data trustworthy, improve quality, and drive utility.
   Key Actions:
       Prioritize data quality to drive ROI by eliminating dark, duplicate, and dirty data.
       Define a clear approach to govern data assets, including roles, responsibilities, processes, and policies.
       Ensure robust data security through strict access controls, encryption, and data loss prevention.
   Measurement: Define and monitor metrics for the adoption of the governance framework, such as data quality scores and data catalogue coverage.


Slide Title: Modernizing Analytics & BI for Self-Service

Slide Content:
   Create a Single Source of Truth: Use tools like Looker and Sigma to establish a centralized, reusable, and accessible source of truth for all users to query.
   Empower Business Users: Convert raw data into meaningful metrics (e.g., using LookML) to allow users across the enterprise to confidently build their own dashboards.
   Balance Empowerment & Control: Enable self-serve BI to empower business users while preserving trust and security through strong, centralized governance.
   Strategic Tooling: Consolidate onto a strategic BI platform (e.g., Tableau, Looker) to provide better tooling and a more consistent user experience.


Slide Title: A Strategic Roadmap for Implementation

Slide Content:
   Phase 1: Strategize & Design:
       Engage stakeholders to align on scope, objectives, and key use cases.
       Establish executive support and secure funding.
       Engage architects early to balance good design with fast time-to-value.
   Phase 2: Activate & Build:
       Create the organizational structure and build the team.
       Establish operating principles, best practices, and provide training.
   Phase 3: Optimize & Sustain:
       Map data initiatives to measurable business outcomes and shared KPIs.
       Measure success, share success stories, and ensure continuous value creation.


</output>

<input>
Large Text: Lack of personalized, targeted marketing GMP+ Google Cloud Understand the customer journey, predict marketing outcomes and personalize the customer experience. Enable 360 consumer insights and personalization at scale Consumer Data Platform Make intelligent recommendation s based on customer journey triggers.
Google Cloud security best practices provide a solid yet flexible approach that can include traditional perimeter security or more complex and granular defense-in-depth approach. Intro to data security and governance helps you understand data governance, and what controls you might need to secure BigQuery resources.
Introducing Looker, Google Cloud&#39;s cutting-edge data analytics platform, designed to empower Customer with actionable insights. Looker, seamlessly integrated with Google Cloud products like BigQuery and DataPlex, provides a centralized platform to harness the power of your data. .
Enterprise: A Looker (Google Cloud core) product with enhanced security features for a wide variety of internal BI and analytics use cases that includes one production instance, 10 standard users, 2 developer users, upgrades, up to 100000 query-based API calls per month, and up to 10000 administrative API calls per month.
Go deep down the GenAI road with Gemini Gemini in Looker is a product in the Gemini for Google Cloud portfolio that provides generative AI-powered assistance to help you work with your data. When Gemini in Looker is enabled, Customer can interact with Looker (Google Cloud core) instance.
Instead of creating vendor lock-in, Google Cloud provides companies with options for simple, streamlined integrations with on-premises environments, other cloud offerings and even the Edge to form a truly hybrid cloud: BigQuery Omni removes the need for data to be ported from one environment to another and instead takes the analytics to the data regardless of the environment Apache Beam, the SDK leveraged on Dataflow, provides transferability and portability to runners like Apache Spark and Apache Flink For organizations looking to run Apache Spark or Apache Hadoop, Google Cloud provides Dataproc Most data users care about what data they have, not which system it resides in. Having access to the data they need when they need it is the most important thing. So for the most part, the type of platform does not matter for users, so long as they are able to access fresh, usable data with familiar tools—whether they are exploring datasets, managing sources across data stores, running ad hoc queries, or developing internal business intelligence tools for executive stakeholders. image of relevant products Emerging trends Continuing on this idea of the convergence of a data lake and a data warehouse into a unified analytics data platform, there are some additional data solutions that are gaining traction.
● Consumer Insights - Break down data silos and create a holistic view of the customer to drive marketing and customer service success with a customer data platform powered by Google. ● Google Marketing Platform - Unlock insights, deliver personalized experiences, and predict consumer behavior faster by combining Google Marketing Platform and other data in Google Cloud.
BigQuery offers significantly lower TCO over alternative cloud-based EDW solutions Upto 54% lower TCO vs alternative solution Eliminate upfront investment and reduce management complexity and operating costs Flexibility to scale up and down to meet changing business needs Source: ESG 2024, Economic Advantage of Google Cloud BigQuery BigQuery AWS Redshift Snowflake Azure Databricks SQL Serverless Up to 54% Lower TCO Upfront Costs (Reservations and Pre-purchased Credits On-demand Cloud Costs Administrative Costs BigQuery is the only native cloud solution that was designed from day one with true serverless and streaming capabilities and has been delivering and refining the tools and processes across 10 years of customer deployments.”
BigQuery&#39;s serverless architecture lets you use languages like SQL and Python to answer your organization&#39;s biggest questions with zero infrastructure management. BigQuery provides a uniform way to work with both structured and unstructured data and supports open table formats like Apache Iceberg, Delta, and Hudi.
BigQuery offers significantly lower TCO over alternative cloud-based EDW solutions Source: ESG 2024, Economic Advantage of Google Cloud BigQuery BigQuery AWS Redshift Snowflake Azure Databricks SQL Serverless Up to 54% Lower TCO Upfront Costs (Reservations and Pre-purchased Credits On-demand Cloud Costs Administrative Costs BigQuery is the only native cloud solution that was designed from day one with true serverless and streaming capabilities and has been delivering and refining the tools and processes across 10 years of customer deployments.” Upto 54% lower TCO vs alternative solution Eliminate upfront investment and reduce management complexity and operating costs Flexibility to scale up and down to meet changing business needs.
There&#39;s great emphasis at Google on continuously making these technologies better. BigQuery users get the benefit of continuous improvements in performance, durability, efficiency, and scalability, without downtime and upgrades associated with traditional technologies.
Proprietary &amp; Confidential BigQuery offers up to 54% lower TCO over alternative cloud-based EDW solutions Upto 54% lower TCO vs alternative solution Lower cost and complexity of running ML workloads and GenAI use cases Eliminate upfront investment and reduce operational overhead BigQuery is the only native cloud solution that was designed from day one with true serverless and streaming capabilities and has been delivering and refining the tools and processes across 10 years of customer deployments.” BigQuery AWS Redshift Snowflake Azure Databricks SQL Serverless Up to 54% Lower TCO Upfront Costs (Reservations and Pre-purchased Credits On-demand Cloud Costs Administrative Costs Source: ESG 2024, Economic Advantage of Google Cloud BigQuery.
BigQuery further enhances Iceberg tables with features traditionally associated with proprietary data warehouses, offering high-throughput streaming for zero-latency queries, enhanced table management with automatic data reclustering, and the ability to build advanced ETL use cases with support for multi-table transactions (Preview).
BigQuery offers up to 54% lower TCO over alternative cloud-based EDW solutions BigQuery AWS Redshift Snowflake Azure Databricks SQL Serverless Up to 54% Lower TCO Upfront Costs (Reservations and Pre-purchased Credits On-demand Cloud Costs Administrative Costs Source: ESG 2024, Economic Advantage of Google Cloud BigQuery BigQuery is the only native cloud solution that was designed from day one with true serverless and streaming capabilities and has been delivering and refining the tools and processes across 10 years of customer deployments.” Upto 54% lower TCO vs alternative solution Lower cost and complexity of running ML workloads and GenAI use cases Eliminate upfront investment and reduce operational overhead.
Google Cloud Storage Cross-Cloud Object Storage BigQuery Storage BigQuery Native Tables BigLake Managed Tables BigLake Iceberg Tables Open Lakehouse Fully Managed Lakehouse BigQuery BigLake Iceberg Tables Data in other clouds BigQuery Omni Low-Latency Streaming High-Throughput DML Storage Optimizations Dataplex | Governance at scale Vertex AI Query with your engine of choice Query and share data cross cloud BigQuery Metastore | Serverless catalog.
Proprietary &amp; Confidential | Google Cloud The architectural advantage of BigQuery Highly available, elastic compute (Dremel) Replicated, durable, distributed storage (Colossus) Distributed memory shuffle tier (MindMeld) Petabit network (Jupiter) SQL API REST API JDBC, ODBC Web UI, CLI Libraries (7 languages) Streaming ingest Free bulk loading Foundation Models Spark, Python Decoupled storage and compute Truly serverless Built-in ML.
Proprietary &amp; Confidential | Google Cloud The architectural advantage of BigQuery Decoupled storage and compute Highly available, elastic compute (Dremel) Replicated, durable, distributed storage (Colossus) Analytics Hub enables real time access to datasets from other projects/organizations Data providers can securely share a dataset with thousands of subscribers with zero-copying.
Unified Data &amp; AI Platform BigQuery Unified Data and AI Governance Multi-Engine (bring multiple engines to a single copy of data) SQL Spark, Python Search, Remote functions Infrastructure Google Cloud Infrastructure (GPUs/TPUs/Silicon) | Open Ecosystem Foundation Models AI Foundation (Google &amp; 3rd party models) GenAI APIs &amp; Studio Text Chat Code Video Image Sound Unified UX (for all data teams) BigQuery Studio + Gemini for Google Cloud Structured Unstructured Data Sharing Multi-Modal Storage (for all types, open data formats &amp; locations) Open Data Formats Cross-Cloud Data Federation BigQuery Managed Storage Google Cloud Storage Vertex AI ML Ops Semi-Structured Streaming.
○ Ensure robust data security and privacy through strict access controls, encryption, data masking, and data loss prevention technologies.
Evaluate your cloud migration options Devise your migration strategy that empowers both the business and IT. Understand the principles of cost optimization Discover five ways to reduce overall cloud spend with a cost optimization strategy. Designing Cloud Teams How to Build a Better Cloud Center of Excellence.
Here&#39;s how to build a robust data and AI governance framework: Prioritize data quality to drive ROI Rise above architecture for compliance and efficiency Banish dark, duplicate, and dirty data to maximize ROI Govern AI models in production 66% of organizations have at least half of their data dark, posing significant risk4 4 Recent Google Cloud survey of IT Decision Makers and Influencers from organizations 500+ with AI workload use or interest.
Having visibility into the amount of engineering effort as well as potential cost savings can help your team establish its priorities. Some customers focus solely on innovation and speed of migration for years on end, and over time their bad optimization habits compound, leading to substantial waste.
GCP Reference Architecture for YOUR_COMPANY&#39;s Data Strategy Data Governance Layer Management Data Lineage Data Security &amp; Access Data Quality Data Discovery Observability Data Logging Data SRE Data Monitoring Data Alerting Orchestration Pipeline Scheduling &amp; Monitoring Data Processing Layer Data Exchange ( Structured Data Sharing) Data Transformation (Streaming &amp; Batch) Hadoop Toolsets Spark Analytics SQL Analytics Analytics Hub BigQuery Dataproc Dataflow Dataplex Cloud Monitoring Cloud Logging Information Schema Cloud Composer Data Consumption Layer Data Products Data Science (MLOPS, Notebook) Plant Operators Business Users Data Ingestion Layer Oracle db Real Time Telematics Batch Data Edge Data Edge Gateway BigQuery Managed Storage Pub Sub Cloud Storage AWS S3 Azure Blob Storage Vertex AI AutoML Looker Studio Looker Cloud Object Storage (Hudi, Parquet, Delta, Iceberg) Multi Cloud Object Storage (Unstructured / Structured / Semi Structured) Cloud Object Storage (Hudi, Parquet, Delta, Iceberg) Managed Storage (Structured / Semi Structured Data) Multi Cloud Object Storage (Unstructured / Structured / Semi Structured) Managed Storage (Structured / Semi Structured Data) Transform &amp; Enrich Transform &amp; Enrich Bigquery Domain Industrial Industrial Dataset Domain Customer Customer Dataset Domain Operations Operations Dataset Enriche Zone RAW Zone Google Ecosystem Channel Activation.
Having a unified, flexible, scalable and cost effective data platform for managing and analyzing data is a crucial part of any company&#39;s success. For example, fully managed database services can enhance the performance, scalability and reduce the overall cost of operation in the cloud.
Cost optimization with Google Cloud Google Cloud helps increase operational efficiency and optimize IT and marketing spend Migrating applications to Google Cloud can save up to 32% (vs. on-prem) Project-level billing provides visibility into the ROI of specific initiatives.
● With Custom sized instances, save upto +50% ● Execute industrial scale ML 27x faster &amp; at 38% lower costs ● GCP VM and Data warehouse maintenance occurs transparently, without downtime &amp; performance impact No Lock in ● Google Cloud offers software based hybrid and multi-cloud solutions for example customers can run BigQuery on on GCP, AWS or Azure.
● Eliminate the limitations of fixed infrastructure and avoid costly overprovisioning. ● Support business growth and handle peak workloads with ease. Cost Savings ● Reducing the licensing costs and lower your total cost of ownership (TCO).

Agenda: Google Cloud Data Solutions.

Number of Slides: 3
</input>

<output>
Slide Title: Google Cloud's Unified Data & AI Platform

Slide Content:
   A flexible, scalable, and cost-effective platform for managing and analyzing all data types.
   Unified Experience: BigQuery Studio and Gemini provide a single interface for all data teams to work with structured, unstructured, and multi-modal data.
   Multi-Engine & Open Formats: Bring multiple engines (SQL, Spark, Python) to a single copy of data and leverage open formats like Iceberg, Delta, and Hudi.
   Integrated AI & ML: Built on Google's powerful infrastructure (GPUs/TPUs) with native access to Foundation Models, Vertex AI, and GenAI capabilities.
   End-to-End Governance: Dataplex provides unified data lineage, security, quality, and discovery across the entire data estate.


Slide Title: BigQuery: The Serverless Data Warehouse

Slide Content:
   A cost-effective, fully-managed data warehouse with up to 54% lower Total Cost of Ownership (TCO) than alternatives.
   Serverless Architecture: Decoupled storage and compute eliminates infrastructure management and auto-scales to meet demand, from gigabytes to petabytes.
   Lower Costs: Eliminate upfront investment, reduce operational overhead, and lower the complexity of running ML and GenAI workloads.
   Multi-Cloud Freedom: No lock-in. Analyze data where it resides with BigQuery Omni, which runs on Google Cloud, AWS, and Azure.
   Built-in Intelligence: Continuously improves performance and efficiency without downtime. Includes built-in ML, streaming capabilities, and real-time analytics.


Slide Title: Actionable Insights with Looker & GenAI

Slide Content:
   Empower teams with a cutting-edge analytics platform to gain actionable insights and drive business outcomes.
   Looker for Centralized BI: Provides a centralized platform for internal BI and analytics, seamlessly integrated with BigQuery and DataPlex to create a single source of truth.
   Gemini for AI-Assisted Analytics: Gemini in Looker provides generative AI assistance, helping users interact with and understand their data more intuitively.
   360-Degree Consumer Insights: Break down data silos by combining GMP data with other sources to understand the customer journey, predict outcomes, and deliver personalized experiences at scale.
   
   
</output>

<input>
Large Text: Take a Platform &amp; Product approach to scale AI: Make your AI Strategy secure, scalable &amp; engaging. Embed AI talent Ensure product teams have access to talent to embed AI Democratize access to AI: Prioritize making AI available to all through no / lo code applications.
Get AI-powered overviews and easily ask follow-ups Supercharging Search Powering Conversational AI Simplify complex topics, learn new skills or speed up everyday tasks according to your needs Use GenAI to do much more with the new Magic Editor experience Magic Photos Josh In the last year, AI has changed Consumer Experiences How we&#39;re entering the enterprise-ready era with AI at scale How we&#39;ve adapted.
Enhance Associate &amp; Employee productivity Drive operational efficiencies ● Simplify search, discoverability, &amp; cart building ● Enable digital clienteling through multimodal conversational commerce ● Accelerate new product design &amp; claims development ● Help write and debug code, emails &amp; build presentations ● Create a multimodal conversational helpdesk with all enterprise knowledge ● Democratize code free data science ● Leverage digitization to reduce leakage &amp; fraud across stores, supply chain, HR &amp; finance ● Unlock insights for Merchants, Supply Chain analysts &amp; more ● Reduce shrink with digital QA of produce ● Streamline marketing briefs, content, images &amp; descriptions ● Automate, campaign building, segmentation &amp; optimization ● Enabler cross channel hyper personalization at scale Google Cloud&#39;s AI Platform Leveraging AI &amp; Google&#39;s ecosystem to deliver value Delight Guests &amp; Consumers alike Optimize &amp; scale media, advertising &amp; CRM Enhance Associate &amp; Employee productivity Drive operational efficiencies.
Address ethical &amp; security considerations Mitigate biases, prioritize data privacy &amp; comply with regulations Democratize access to AI Prioritize making AI available to all through no / lo code applications Embed AI talent Ensure product teams have access to talent to embed AI.
How do we make it easier for Marketers to find the right solution? AI Toolbox Self-serve solution to provide solutions across the end-to-end Marketing workflows incl. low-lift creative production. The challenge AI Solution Analyse Create.
How do we keep up with the latest advancements and ensure we&#39;re not falling behind? Solution ● We need to embrace agility and continuous learning. Staying informed about new tools, techniques, and research will allow us to adapt quickly and leverage the most effective AI solutions for our business.
This means collaborating across different departments (legal, risk, IT, etc.) from the outset. By addressing potential roadblocks early on, we can ensure a smoother transition and realize the full potential of our AI investments.
AI holds enormous $7trillion potential to revolutionize how we work. 40% of working hours across industries could be augmented by generative AI. Source: Accenture/MIT eBook, 2023, Goldman Sachs Research, 2023 2) McKinsey: The Economic Potential of GenAI 2023 $270B Banking.
Transform Marketing with Generative AI It used to be difficult for marketers and product teams to scale because all the creative work was manual. But now, with Google Cloud&#39;s AI technology, marketers can harness Generative AI to create highly personalized content for specific audiences.
Generative AI is driving new opportunities Operational efficiencies, cost savings, and value creation Improve time-to-value to search, navigate, and extract insights and understanding from large amounts of complex data Complex data, intuitively accessible Improve customer experience, reaching larger client bases by making online interactions more natural, conversational, and rewarding Online interactions made conversational Generate text, code, image, video, or music quickly and multi-modally, speeding up every business process and maximizing employee productivity Content generation at the click of a button Customize large models and incorporate state of the art generative capabilities natively into your own internal ML operational platforms Customize Foundational models Analyst Customer Service Creative AI Practitioner.
Digital Commerce Product Recommendations Generate and action on prescriptive marketing insights aimed to help extracting maximum per-consumer value over their lifetime and minimizing churn Consumer Lifetime Value Optimization Help predict customers who are most likely to make a purchase, so that you can personalize communications with them Propensity to Convert Modeling Utilize consumer insights and analytics to understand and predict trends to help identify promising product innovation / renovation areas early Trend Spotting Create content, copy, images across all marketing efforts to optimize for speed, efficiency and costs Generative AI Harness insights from consumer sentiment across platforms and other data sources to inform your product innovation using AI/ ML Sentiment Analysis 07 08 09 10 11 12 Hyper Personalization Hyper Relevance - .
Deliver growth and productivity with Generative AI for marketing Generate text, image, and audio tailored for each of your channels and take advantage of fine-tuning foundation and OSS models to align with brand guidelines, accelerating content development Creative &amp; Content Generation Unlock personalization for enhanced segments and at previously unmanageable scale for creative and catalog/site content Media Performance &amp; Personalization Democratize data analysis, and assistive capabilities for repetitive tasks to help boost marketer productivity and collaboration Measurement &amp; Insights 1 2 3 - . .
Understand, conceptualize, and construct consumer profiles, including Gender, Age, InMarket, Affinity, Channels, Categories, Behavioral and other attributes.
Easily build predictive and lifetime value audience segments to optimize marketing spend &amp; drive ROI with data-driven insights Generate scaled creation of personalized content and creative variants with AI and adapt as consumer behavior changes Develop a holistic view of consumers Use AI to build predictive audiences Help increase efficiency and unlock creativity with generative AI.
Creative analysis to personalize ads Marketing Analytics - Media Performance Durable Data Google Cloud Predictive AI Personalize Ingest creatives into the cloud Apply AI models to label content of video, display, and text creatives at high levels of detail and consistency and match with ad performance Align creative content and messaging that resonates most with in-market audiences to maximize performance and engagement 01 02 03 Decrease in Cost Per View (CPV) Increase consumer engagement 20% 24%
Drive predictive growth with AI Enrich targeting &amp; measurement Monetize your audience Get started Innovate with Gen AI GCP Data and AI Platform Helping customers own their data &amp; turn marketing into an AI-powered growth engine Data &amp; AI Cloud for Marketing Customer 360 with AI-Powered Ads Centralize 1P data in BigQuery &amp; activate real-time Ads based on predictive AI to business value (eg LTV) Data Clean Room with AI-Powered Ads Enable privacy-centric data sharing to create new AI-driven measurement &amp; audiences Media Network Platform Create high-margin business by monetizing audiences &amp; media assets using Ad Manager, GMP &amp; BigQuery GenAI for Marketing Drive new data &amp; creative innovation using the latest Generative AI solutions Analyze Centralize Model Activate Reach Manage Measure Centralize &amp; Clean Data AI-Powered Ads &amp; more Combine &amp; join without copying or moving underlying data Assign Values using ML Executable Workshops Quickly identify high value use cases for implementation 1. Kick Off 2. Interviews 3. Use Case Workshop 4. Value &amp; Impact and Report 5. Implementation Proposal Workshop/assessments.
What we have learned about AI success There are five key challenges that organisations must overcome to successfully deploy AI Ensuring security, compliance &amp; privacy Unlocking disparate data sources Reducing cost &amp; complexity It&#39;s a journey, not once-off Driving innovation and efficiency.
What we have learned about AI success There are five key challenges that organisations must overcome to successfully deploy AI Ensuring security, compliance &amp; privacy Unlocking disparate data sources Reducing cost &amp; complexity It&#39;s a journey, not once-off Accelerating sustainability to drive impact.
Speed data-intensive processes Automate manual processes Streamline repetitive tasks Accelerate review of disparate data sources Generative AI can be applied to re-shape process and experiences Optimize Accessible information New experiences Real time personalization Transform.
● Using GenAI to simply reduce costs without enabling human innovation means you miss the huge benefits and transformational opportunities.

Agenda: Re-imagine new product innovation and marketing workflows with AI.

Number of Slides: 2
</input>

<output>
Slide Title: Transform Marketing Workflows with Generative AI

Slide Content:
   Accelerate Content Creation: Use GenAI to generate tailored text, images, and audio for each channel, aligning with brand guidelines and dramatically speeding up content development.
   Unlock Hyper-Personalization: Go beyond traditional segmentation. Use AI to create and scale personalized content and creative variants for highly specific audiences.
   Enhance Media Performance: Analyze creative content with AI to understand what resonates with audiences, enabling data-driven decisions that increase engagement and decrease cost per view.
   Boost Marketer Productivity: Democratize data analysis and automate repetitive tasks, freeing up marketers to focus on strategy and collaboration.
   Predict Consumer Behavior: Leverage predictive AI to model propensity to convert and customer lifetime value, optimizing marketing spend and driving ROI.


Slide Title: AI-Driven Product Innovation & Strategy

Slide Content:
</output>"""
  )
  si_text1 = f"""You are a slide creator. You will be given a large text, an agenda and the number of slides to be generated per each agenda.. Your task is to create not more than {number_of_slides} slides for the given agenda with the help of the given text."""

  model = config["default"]["GEMINI_MODEL"]
  contents = [
      types.Content(role="user", parts=[msg1_text1]),
  ]

  generate_content_config = types.GenerateContentConfig(
      temperature=1,
      top_p=1,
      seed=0,
      max_output_tokens=65535,
      safety_settings=[
          types.SafetySetting(
              category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
          ),
          types.SafetySetting(
              category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
          ),
      ],
      system_instruction=[types.Part.from_text(text=si_text1)],
  )
  text_chunks = []
  for chunk in client.models.generate_content_stream(
      model=model,
      contents=contents,
      config=generate_content_config,
  ):
    if not chunk.candidates or not chunk.candidates[0]:
      continue
    content = chunk.candidates[0].content
    if not content or not content.parts:
      continue

    for part in content.parts:
      if hasattr(part, "text") and part.text:
        text_chunks.append(part.text)

  final_response = "".join(text_chunks)

  return final_response


def content_generation(agenda, url_list):
  ensemble_retriever = ensemble_retriver(url_list)

  print(f"Processing Agenda: {agenda}...")

  number_of_slides = agenda[1]

  questions = generate_questions(agenda[0])
  # print("\nquestions:\n",questions)

  pattern = r"\d+\.\s+(.*)"
  questions_list = re.findall(pattern, questions)
  # print("\nquestions_list:\n",questions_list)

  results = ensemble_retriever.batch(questions_list)
  # print("\nresults:\n",results)

  separator = "\n"
  all_content_string = separator.join(
      [doc["page_content"] for doc_list in results for doc in doc_list]
  )
  # print("\nall content string:\n",all_content_string)
  source_urls = []

  for doc_list in results:
    for doc in doc_list:
      url = doc["metadata"].get("url")
      name = doc["metadata"].get("name")

      if url and name:
        source_urls.append({"name": name, "url": url})
  # number_of_slides=3
  generated_content = generate_contents(
      all_content_string, agenda[0], number_of_slides
  )
  # print("\ngenerated_content:\n",generated_content)
  # print(type(generated_content))

  return generated_content, source_urls


def run_parallel_task(task_assigned, url_list):
  print(f"Task assigned: {task_assigned}\n")
  final_generated_content, sources = content_generation(task_assigned, url_list)

  return {
      "title": task_assigned[0],
      "content": final_generated_content,
      "sources": sources,
  }


def run_cust_task(task_assigned, customer_name, objective):
  print(f"Task assigned: {task_assigned}\n")
  final_generated_content = generate_cust_info(customer_name, objective)
  sources = []

  return {
      "title": task_assigned,
      "content": final_generated_content,
      "sources": sources,
  }


def gen_text(task_list, url_list):
  final_generated_contents = {}
  source_urls = {}
  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [
        executor.submit(run_parallel_task, task_assigned, url_list)
        for task_assigned in task_list
    ]
    for future in concurrent.futures.as_completed(futures):
      final_generated_content = future.result()
      final_generated_contents[final_generated_content["title"]] = (
          final_generated_content["content"]
      )
      source_urls[int(final_generated_content["title"].split(": ")[0])] = (
          final_generated_content["sources"]
      )

  formatted_content = ""
  final_source_urls = {}
  for key, value in sorted(
      final_generated_contents.items(), key=lambda x: int(x[0].split(":")[0])
  ):
    slide_number = key.split(": ")[0]
    if slide_number.isdigit():
      slide_number = int(slide_number)

    formatted_content += (
        f"-----Task {slide_number} Completed successfully-----\n\n"
    )
    formatted_content += value + "\n\n"
    title = key.split(": ")[1]
    slide_number = str(slide_number)
    if slide_number[:-1] in final_source_urls.keys():
      final_source_urls[slide_number[:-1]].extend(
          source_urls[int(slide_number)]
      )
    else:
      final_source_urls[slide_number[:-1]] = source_urls[int(slide_number)]

    seen = set()
    unique_data = []
    for url_item in final_source_urls[slide_number[:-1]]:
      item_tuple = tuple(url_item.items())
      if item_tuple not in seen:
        seen.add(item_tuple)
        unique_data.append(url_item)
    final_source_urls[slide_number[:-1]] = unique_data

  return formatted_content, final_source_urls
