
Here is a break down of a massive example command, step-by-step to see how report_builder.py should handle each part based on its current code.

Command:

python3 report_builder.py \
--topic "Artificial Intelligence in Healthcare" \
--keywords "AI diagnostics, machine learning drug discovery" \
--guidance "Please prioritize using information found that is at least based on January 2025 and newer. Do not include anything in the context that is before October 2024." \
--max-web-results 6 \
--per-keyword-results 3 \
--max-reddit-results 3 \
--max-reddit-comments 10 \
--from_date 2025-04-07 \
--to_date 2025-04-14 \
--direct-articles test_example/direct_urls.txt \
--score-threshold 6 \
--reference-docs test_example/llm-news.txt \
--reference-docs-folder research/Example_Docs_Folder

Analysis of Each Argument:

--topic "Artificial Intelligence in Healthcare"

What it does: Sets the main theme for the report. Used in AI prompts for discovering sources, summarizing content, and generating the final report.
Will it work? Yes. This is a fundamental, required argument and the script uses it correctly.


--keywords "AI diagnostics, machine learning drug discovery"

What it does: Provides the specific search terms. The script will use these to:
Ask the AI to discover relevant sources (websites, subreddits).
Search within discovered website sources using search APIs (e.g., site:example.com "AI diagnostics").
Search within discovered Reddit sources using Selenium.
Will it work? Yes. The script handles comma-separated keywords and will treat "AI diagnostics" and "machine learning drug discovery" as two separate search concepts.


--guidance "Please prioritize using information found..."

What it does: Appends this text to the prompts sent to the AI during the summarization and final report generation phases.
Will it work? Yes, technically. The script will include this text in the prompts. However, the effectiveness of the date filtering part ("Jan 2025 and newer", "not before Oct 2024") depends heavily on the LLM's ability to understand and apply these temporal constraints based only on the text content it's summarizing or writing about. It might struggle to accurately date information within the scraped text and adhere strictly. The --from_date/--to_date args are more reliable for filtering search results.


--max-web-results 6

What it does: Limits the total number of articles scraped from any single website source (e.g., if nature.com is discovered). Even if searching for both keywords finds 10 relevant articles on nature.com, the script will only attempt to scrape the top 6 unique URLs found.
Will it work? Yes. The script uses this value to limit scraping attempts per website domain.


--max-reddit-results 3

What it does: Limits the number of Reddit posts scraped per discovered subreddit (e.g., r/machinelearning). If searches find 10 relevant posts, only the top 3 unique posts will have their content (title, body, comments) scraped.
Will it work? Yes. The script uses this value to limit how many posts are processed per subreddit.
--max-reddit-comments 10

What it does: Limits the number of comments scraped from each individual Reddit post that is selected for scraping.
Will it work? Yes. The script uses this value when extracting comments from a post page.


--per-keyword-results 3

What it does: Specifies how many results to request from the search API (Google/Brave) for each individual keyword search within a website source. For example, it will ask for 3 results for site:example.com "AI diagnostics" and another 3 results for site:example.com "machine learning drug discovery". The combined unique results are then capped by --max-web-results (6 in this case).
Will it work? Yes. The script uses this to control the number of results requested per API call.


--from_date 2025-04-07 & --to_date 2025-04-14

What they do: Instruct the search APIs (Google/Brave) to return only results indexed within this specific date range.
Will it work? Yes. The script correctly formats these dates for the respective API calls. This is the most reliable way to filter by date at the search stage.


--direct-articles "https://ai-news.com/ai-healthycare,https://ai-news.com/ai-healthynews"

What it does: Provide specific URLs to scrape directly, without API searching within them.
Will it work? Yes as long as you followthe collowing format for this calls:
Create a text file (e.g., direct_urls.txt) with:
https://ai-news.com/ai-healthycare
https://ai-news.com/ai-healthynews
Then use --direct-articles direct_urls.txt in your command.


--score-threshold 6

What it does: Sets the minimum relevance score (0-10) a summary must receive from the AI to be included in the context for the final report generation.
Will it work? Yes. We fixed this recently. Summaries scoring 5 or less will be discarded before generating the report.


--reference-docs llm-news.txt

What it does: Tells the script to load the content from the file llm-news.txt (assuming it's a txt, pdf, or docx file) and use its content as reference material.
Will it work? Yes, assuming llm-news.txt exists in the working directory or a specified relative path and is a supported format.


--reference-docs-folder research/Example_Docs_Folder

What it does: Tells the script to look inside the research/Example_Docs_Folder directory, find all supported files (txt, pdf, docx), and load their content as additional reference material.
Will it work? Yes, assuming the folder research/Example_Docs_Folder exists relative to where you run the script and contains supported file types.
