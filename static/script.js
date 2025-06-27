document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded event fired.'); // Debug log
    const reportForm = document.getElementById('report-form');
    const generateButton = document.getElementById('generate-button');
    const processStatusDiv = document.getElementById('process-status');
    const stopButton = document.getElementById('stop-button');
    const loadingSpinner = document.getElementById('loading-spinner');
    const timerSpan = document.getElementById('timer');
    const outputDiv = document.getElementById('output').querySelector('pre');
    const resultsDiv = document.getElementById('results');
    const reportLinksDiv = document.getElementById('report-links');
    const llmModelSelect = document.getElementById('llm-model');

    // Easy Mode elements
    const easyModeButton = document.getElementById('easy-mode-button');
    const easyModeModal = document.getElementById('easy-mode-modal');
    const closeModalButton = easyModeModal.querySelector('.close-button');
    const researchDescriptionTextarea = document.getElementById('research-description');
    const easyModeLlmModelSelect = document.getElementById('easy-mode-llm-model'); // New LLM select for easy mode
    const submitResearchDescriptionButton = document.getElementById('submit-research-description');
    const easyModeStatusDiv = document.getElementById('easy-mode-status');
    const easyModeSpinner = document.getElementById('easy-mode-spinner');
    const easyModeMessageSpan = document.getElementById('easy-mode-message');
    const topicInput = document.getElementById('topic');
    const keywordsInput = document.getElementById('keywords');
    const guidanceTextarea = document.getElementById('guidance');
    const fadingMessagePopup = document.getElementById('fading-message-popup');

    const referenceDocsDropArea = document.getElementById('reference-docs-drop-area');
    const referenceDocsList = document.getElementById('reference-docs-list');
    const referenceDocsInput = document.getElementById('reference-docs');
    let uploadedReferenceDocs = []; // Store paths of uploaded reference docs


    const directArticlesUrlInput = document.getElementById('direct-articles-url');
    const addArticleUrlButton = document.getElementById('add-article-url');
    const directArticlesList = document.getElementById('direct-articles-list');
    const directArticlesUrlsHiddenInput = document.getElementById('direct-articles-urls');
    let directArticleUrls = []; // Store URLs


    let startTime;
    let timerInterval;

    function startTimer() {
        startTime = new Date().getTime();
        timerInterval = setInterval(updateTimer, 1000);
        loadingSpinner.style.display = 'block';
        stopButton.style.display = 'inline-block'; // Show stop button
    }

    function stopTimer() {
        clearInterval(timerInterval);
        loadingSpinner.style.display = 'none';
        stopButton.style.display = 'none'; // Hide stop button
    }

    function updateTimer() {
        const currentTime = new Date().getTime();
        const elapsedTime = currentTime - startTime;
        const hours = Math.floor(elapsedTime / (1000 * 60 * 60));
        const minutes = Math.floor((elapsedTime % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((elapsedTime % (1000 * 60)) / 1000);

        timerSpan.textContent =
            `${String(hours).padStart(2, '0')}:` +
            `${String(minutes).padStart(2, '0')}:` +
            `${String(seconds).padStart(2, '0')}`;
    }

    function displayTotalDuration() {
        // The timer span already shows the total duration when stopped
        // No additional action needed here unless a separate display is desired
    }

    function resetProcessStatus() {
        generateButton.disabled = false;
        processStatusDiv.style.display = 'none';
        timerSpan.textContent = '00:00:00';
    }

    // --- Helper Functions for Drag and Drop ---
    function preventDefaults(event) {
        event.preventDefault();
        event.stopPropagation();
    }

    function highlight(element) {
        element.classList.add('highlight');
    }

    function unhighlight(element) {
        element.classList.remove('highlight');
    }

    function handleDrop(event, dropArea, fileInput, fileListElement = null, filePathElement = null, isSingleFile = false) {
        const dt = event.dataTransfer;
        let files = dt.files;

             if (isSingleFile && files.length > 1) {
                  alert("Please drop only one file.");
                  filePathElement.textContent = '';
                  if (fileListElement) fileListElement.innerHTML = '';
                  if (isSingleFile && filePathElement) filePathElement.textContent = '';
                  fileInput.value = ''; // Clear the file input
                  if (isSingleFile && dropArea === directArticlesDropArea) uploadedDirectArticlesFile = null;
                  return;
             }

             if (fileListElement) {
                 fileListElement.innerHTML = ''; // Clear previous list for multiple files
             }
             if (filePathElement) {
                 filePathElement.textContent = ''; // Clear previous path for single file
             }

             const fileList = [];
             for (let i = 0; i < files.length; i++) {
                 const file = files[i];
                 fileList.push(file);
                 if (fileListElement) {
                     const listItem = document.createElement('li');
                     listItem.textContent = file.name;
                     const removeButton = document.createElement('span');
                     removeButton.textContent = 'x';
                     removeButton.classList.add('remove-file');
                     removeButton.onclick = function() {
                         // Remove from list and potentially from a temporary storage if implemented
                         listItem.remove();
                         // Note: Removing from the visual list doesn't remove from the input's FileList directly.
                         // We'll handle the actual files to upload when the form is submitted.
                         // For now, rely on the input.files or a separate array if needed.
                     };
                     listItem.appendChild(removeButton);
                     fileListElement.appendChild(listItem);
                 }
                 if (isSingleFile && filePathElement) {
                     filePathElement.textContent = `File: ${file.name}`;
                 }
             }

             // Assign the dropped files to the corresponding file input element
             fileInput.files = files;

             // Store the file names/paths temporarily. Actual paths will come from backend after upload.
             if (dropArea === referenceDocsDropArea) {
                 uploadedReferenceDocs = Array.from(files).map(f => f.name); // Store names for display
             }

        unhighlight(dropArea);
    }

    // --- Event Listeners for Drag and Drop ---

    // Reference Docs (Multiple Files)
    // Reference Docs (Multiple Files) - Event Listeners
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, () => highlight(referenceDocsDropArea), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, () => unhighlight(referenceDocsDropArea), false);
    });

    referenceDocsDropArea.addEventListener('drop', (e) => handleDrop(e, referenceDocsDropArea, referenceDocsInput, referenceDocsList, null, false), false);

    // Allow clicking the drop area to open file dialog
    referenceDocsDropArea.addEventListener('click', () => referenceDocsInput.click());
    referenceDocsInput.addEventListener('change', function() {
         handleDrop({ dataTransfer: { files: this.files } }, referenceDocsDropArea, this, referenceDocsList, null, false);
    });




    // --- Handle Direct Articles URL Input ---
    addArticleUrlButton.addEventListener('click', function() {
        const url = directArticlesUrlInput.value.trim();
        if (url) {
            addUrlToList(url);
            directArticlesUrlInput.value = ''; // Clear input
        }
    });

    function addUrlToList(url) {
        if (!directArticleUrls.includes(url)) {
            directArticleUrls.push(url);
            const listItem = document.createElement('li');
            listItem.textContent = url;
            const removeButton = document.createElement('span');
            removeButton.textContent = 'x';
            removeButton.classList.add('remove-file'); // Re-use existing class for styling
            removeButton.onclick = function() {
                listItem.remove();
                directArticleUrls = directArticleUrls.filter(item => item !== url);
                directArticlesUrlsHiddenInput.value = directArticleUrls.join('\n'); // Update hidden input
            };
            listItem.appendChild(removeButton);
            directArticlesList.appendChild(listItem);
            directArticlesUrlsHiddenInput.value = directArticleUrls.join('\n'); // Update hidden input
        }
    }


    // --- Load LLM Models for Dropdown ---
    async function loadLlmModels() {
        try {
            const modelsResponse = await fetch('/get_llm_models');
            const modelsData = await modelsResponse.json();
            console.log('LLM Models Data:', modelsData); // Debug log

            if (modelsData.llm_models) {
                 // Populate main LLM model select
                 llmModelSelect.innerHTML = '<option value="">Select a model</option>'; // Clear existing
                 modelsData.llm_models.forEach(modelKey => {
                      const option = document.createElement('option');
                      option.value = modelKey;
                      option.textContent = modelKey;
                      llmModelSelect.appendChild(option);
                 });

                 // Populate easy mode LLM model select
                 easyModeLlmModelSelect.innerHTML = '<option value="">Select a model</option>'; // Clear existing
                 modelsData.llm_models.forEach(modelKey => {
                      const option = document.createElement('option');
                      option.value = modelKey;
                      option.textContent = modelKey;
                      easyModeLlmModelSelect.appendChild(option);
                 });
            }

        } catch (error) {
            console.error('Error loading LLM models:', error);
        }
    }

    console.log('Calling loadLlmModels...'); // Debug log
    // Call loadLlmModels when the page loads
    loadLlmModels();


    // --- Handle Form Submission ---
    reportForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        // Disable generate button, show process status, start timer
        generateButton.disabled = true;
        processStatusDiv.style.display = 'flex'; // Use flex to align items
        startTimer();

        const formData = new FormData(reportForm);

        // Append uploaded files to the FormData
        // Note: The file inputs already hold the dropped/selected files due to handleDrop
        // formData.append('reference-docs', referenceDocsInput.files); // This appends FileList, which FormData handles
        // Append direct article URLs as a single string
        formData.append('direct-articles-urls', directArticleUrls.join('\n'));

        // Clear previous output and results
        outputDiv.textContent = '';
        resultsDiv.style.display = 'none';
        reportLinksDiv.innerHTML = '';

        // Send data to backend
        try {
            const response = await fetch('/generate_report', {
                method: 'POST',
                body: formData
            });
 
            outputDiv.textContent = 'Starting report generation...\n';
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    console.log('Stream complete');
                    break;
                }
                buffer += decoder.decode(value, { stream: true });

                // Process each complete SSE message
                const messages = buffer.split('\n\n');
                buffer = messages.pop(); // Keep incomplete message in buffer

                for (const message of messages) {
                    if (message.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(message.substring(6));
                            if (data.type === 'output') {
                                outputDiv.textContent += data.content;
                                outputDiv.scrollTop = outputDiv.scrollHeight;
                            } else if (data.type === 'complete') {
                                outputDiv.textContent += "\n--- Process Complete ---\n";
                                resultsDiv.style.display = 'block';
                                reportLinksDiv.innerHTML = '';
                                if (data.report_files && data.report_files.length > 0) {
                                    data.report_files.forEach(file => {
                                        const link = document.createElement('a');
                                        link.href = `/reports/${file.split('/').pop()}`;
                                        link.textContent = `Download ${file.split('/').pop()}`;
                                        link.target = '_blank';
                                        reportLinksDiv.appendChild(link);
                                        reportLinksDiv.appendChild(document.createElement('br'));
                                    });
                                } else {
                                    reportLinksDiv.textContent = "No report files found.";
                                }
                                stopTimer();
                                displayTotalDuration();
                                resetProcessStatus();
                                reader.cancel(); // Stop reading the stream
                                return; // Exit the function
                            } else if (data.type === 'error') {
                                outputDiv.textContent += `\n--- Error: ${data.content} ---\n`;
                                stopTimer();
                                displayTotalDuration();
                                resetProcessStatus();
                                reader.cancel(); // Stop reading the stream
                                return; // Exit the function
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e, 'Message:', message);
                            // This might be a keep-alive message or malformed JSON, ignore for now
                        }
                    }
                }
            }
            // If the loop finishes without a 'complete' or 'error' type, it means the stream closed unexpectedly
            outputDiv.textContent += '\n--- Connection to output stream closed or error occurred. ---\n';
            stopTimer();
            displayTotalDuration();
            resetProcessStatus();

        } catch (error) {
            console.error('Error submitting form or streaming output:', error);
            outputDiv.textContent = 'An error occurred while submitting the form or streaming output.';
            stopTimer();
            displayTotalDuration();
            resetProcessStatus();
        }
    });

    // --- Easy Mode Logic ---
    easyModeButton.addEventListener('click', function() {
        easyModeModal.style.display = 'block';
        researchDescriptionTextarea.value = ''; // Clear previous input
        easyModeStatusDiv.style.display = 'none'; // Hide status initially
    });

    closeModalButton.addEventListener('click', function() {
        easyModeModal.style.display = 'none';
    });

    window.addEventListener('click', function(event) {
        if (event.target == easyModeModal) {
            easyModeModal.style.display = 'none';
        }
    });

    submitResearchDescriptionButton.addEventListener('click', async function() {
        const description = researchDescriptionTextarea.value.trim();
        if (!description) {
            showFadingMessage('Please provide a description.', 'error');
            return;
        }

        easyModeStatusDiv.style.display = 'flex';
        easyModeSpinner.style.display = 'block';
        easyModeMessageSpan.textContent = 'Generating AI suggestions...';
        submitResearchDescriptionButton.disabled = true;

        const selectedLlmModel = easyModeLlmModelSelect.value; // Use the easy mode specific select
        if (!selectedLlmModel) {
            showFadingMessage('Please select an LLM Model in the popup.', 'error'); // Updated message
            easyModeStatusDiv.style.display = 'none';
            submitResearchDescriptionButton.disabled = false;
            return;
        }

        let attempts = 0;
        const maxAttempts = 3;
        let success = false;

        while (attempts < maxAttempts && !success) {
            attempts++;
            easyModeMessageSpan.textContent = `Generating AI suggestions (Attempt ${attempts}/${maxAttempts})...`;
            try {
                const response = await fetch('/generate_ai_suggestions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        description: description,
                        llm_model: selectedLlmModel
                    }),
                });

                const data = await response.json();

                if (data.status === 'success') {
                    topicInput.value = data.topic || '';
                    keywordsInput.value = data.keywords || '';
                    guidanceTextarea.value = data.guidance || '';
                    showFadingMessage('AI suggestions generated successfully!', 'success');
                    success = true;
                    easyModeModal.style.display = 'none';
                } else {
                    console.error('AI suggestion generation failed:', data.message);
                    if (attempts === maxAttempts) {
                        showFadingMessage(`Failed to generate AI suggestions after ${maxAttempts} attempts: ${data.message}`, 'error');
                    }
                }
            } catch (error) {
                console.error('Error fetching AI suggestions:', error);
                if (attempts === maxAttempts) {
                    showFadingMessage(`An error occurred during AI suggestion generation after ${maxAttempts} attempts.`, 'error');
                }
            }
        }

        easyModeStatusDiv.style.display = 'none';
        easyModeSpinner.style.display = 'none';
        submitResearchDescriptionButton.disabled = false;
    });

    function showFadingMessage(message, type = 'info') {
        fadingMessagePopup.textContent = message;
        fadingMessagePopup.className = 'fading-popup show'; // Reset classes and add 'show'

        if (type === 'success') {
            fadingMessagePopup.style.backgroundColor = 'rgba(40, 167, 69, 0.9)'; // Green
        } else if (type === 'error') {
            fadingMessagePopup.style.backgroundColor = 'rgba(220, 53, 69, 0.9)'; // Red
        } else {
            fadingMessagePopup.style.backgroundColor = 'rgba(0, 123, 255, 0.9)'; // Blue (default)
        }

        setTimeout(() => {
            fadingMessagePopup.classList.remove('show');
        }, 3000); // Message fades out after 3 seconds
    }
});
