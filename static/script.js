document.addEventListener('DOMContentLoaded', function() {
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

    const referenceDocsDropArea = document.getElementById('reference-docs-drop-area');
    const referenceDocsList = document.getElementById('reference-docs-list');
    const referenceDocsInput = document.getElementById('reference-docs');
    let uploadedReferenceDocs = []; // Store paths of uploaded reference docs

    const referenceDocsFolderDropArea = document.getElementById('reference-docs-folder-drop-area');
    const referenceDocsFolderPath = document.getElementById('reference-docs-folder-path');
    const referenceDocsFolderInput = document.getElementById('reference-docs-folder');
    let uploadedReferenceDocsFolder = null; // Store path of the uploaded folder

    const directArticlesDropArea = document.getElementById('direct-articles-drop-area');
    const directArticlesFilePath = document.getElementById('direct-articles-file-path');
    const directArticlesInput = document.getElementById('direct-articles');
    let uploadedDirectArticlesFile = null; // Store path of the uploaded file


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

    function handleDrop(event, dropArea, fileInput, fileListElement = null, filePathElement = null, isFolder = false, isSingleFile = false) {
        const dt = event.dataTransfer;
        let files = [];

        if (isFolder) {
             // For folder drop, we expect a single item which is the folder
             if (dt.items && dt.items.length > 0 && dt.items[0].webkitGetAsEntry) {
                  const entry = dt.items[0].webkitGetAsEntry();
                  if (entry && entry.isDirectory) {
                       // We don't process folder contents here, just indicate a folder was dropped
                       // The actual files will be handled by the backend on upload
                       filePathElement.textContent = `Folder: ${entry.name}`;
                       // Store a placeholder or the folder name for now, actual path comes from backend
                       uploadedReferenceDocsFolder = entry.name; // Placeholder
                       // Clear any previously selected files for this input type
                       fileInput.files = dt.files; // Assign the dropped files/folder to the input element
                  } else {
                       alert("Please drop a single folder.");
                       filePathElement.textContent = '';
                       uploadedReferenceDocsFolder = null;
                       fileInput.value = ''; // Clear the file input
                  }
             } else {
                  alert("Folder upload not supported in this browser.");
                  filePathElement.textContent = '';
                  uploadedReferenceDocsFolder = null;
                  fileInput.value = ''; // Clear the file input
             }
        } else {
             // For file drop
             files = dt.files;

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
             } else if (dropArea === directArticlesDropArea) {
                 uploadedDirectArticlesFile = files.length > 0 ? files[0].name : null; // Store name for display
             }
        }

        unhighlight(dropArea);
    }

    // --- Event Listeners for Drag and Drop ---

    // Reference Docs (Multiple Files)
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, preventDefaults, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, () => highlight(referenceDocsDropArea), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        referenceDocsDropArea.addEventListener(eventName, () => unhighlight(referenceDocsDropArea), false);
    });
    referenceDocsDropArea.addEventListener('drop', (e) => handleDrop(e, referenceDocsDropArea, referenceDocsInput, referenceDocsList, null, false, false), false);
    // Allow clicking the drop area to open file dialog
    referenceDocsDropArea.addEventListener('click', () => referenceDocsInput.click());
    referenceDocsInput.addEventListener('change', function() {
         handleDrop({ dataTransfer: { files: this.files } }, referenceDocsDropArea, this, referenceDocsList, null, false, false);
    });


    // Reference Docs Folder (Single Folder)
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        referenceDocsFolderDropArea.addEventListener(eventName, preventDefaults, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        referenceDocsFolderDropArea.addEventListener(eventName, () => highlight(referenceDocsFolderDropArea), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        referenceDocsFolderDropArea.addEventListener(eventName, () => unhighlight(referenceDocsFolderDropArea), false);
    });
    referenceDocsFolderDropArea.addEventListener('drop', (e) => handleDrop(e, referenceDocsFolderDropArea, referenceDocsFolderInput, null, referenceDocsFolderPath, true, true), false);
     // Allow clicking the drop area to open folder dialog
    referenceDocsFolderDropArea.addEventListener('click', () => referenceDocsFolderInput.click());
    referenceDocsFolderInput.addEventListener('change', function() {
         handleDrop({ dataTransfer: { files: this.files } }, referenceDocsFolderDropArea, this, null, referenceDocsFolderPath, true, true);
    });


    // Direct Articles File (Single .txt File)
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        directArticlesDropArea.addEventListener(eventName, preventDefaults, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        directArticlesDropArea.addEventListener(eventName, () => highlight(directArticlesDropArea), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        directArticlesDropArea.addEventListener(eventName, () => unhighlight(directArticlesDropArea), false);
    });
    directArticlesDropArea.addEventListener('drop', (e) => handleDrop(e, directArticlesDropArea, directArticlesInput, null, directArticlesFilePath, false, true), false);
     // Allow clicking the drop area to open file dialog
    directArticlesDropArea.addEventListener('click', () => directArticlesInput.click());
    directArticlesInput.addEventListener('change', function() {
         handleDrop({ dataTransfer: { files: this.files } }, directArticlesDropArea, this, null, directArticlesFilePath, false, true);
    });


    // --- Load LLM Models for Dropdown ---
    async function loadLlmModels() {
        try {
            const response = await fetch('/'); // Fetch data from the index route
            const text = await response.text(); // Get the HTML content as text
            // We need to parse the HTML to find the data passed by Flask
            // A better approach would be a dedicated endpoint to get models
            // For now, let's assume Flask passes a JS variable or similar
            // Or, we can make a new endpoint /get_llm_models

            // Let's add a new endpoint for this
            const modelsResponse = await fetch('/get_llm_models');
            const modelsData = await modelsResponse.json();

            if (modelsData.llm_models) {
                 llmModelSelect.innerHTML = '<option value="">Select a model</option>'; // Clear existing
                 modelsData.llm_models.forEach(modelKey => {
                      const option = document.createElement('option');
                      option.value = modelKey;
                      option.textContent = modelKey;
                      llmModelSelect.appendChild(option);
                 });
            }

        } catch (error) {
            console.error('Error loading LLM models:', error);
        }
    }

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
        // formData.append('direct-articles', directArticlesInput.files[0]); // Append the single file
        // formData.append('reference-docs-folder', referenceDocsFolderInput.files); // Append the FileList for the folder

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

            const result = await response.json();

            if (response.ok && result.status === 'processing') {
                outputDiv.textContent = result.message + '\n';
                // Start streaming output
                streamOutput();
            } else {
                outputDiv.textContent = 'Error: ' + result.message + '\n' + (result.errors || '');
                stopTimer(); // Stop timer on backend error
                displayTotalDuration(); // Display duration on backend error
                resetProcessStatus(); // Reset button/spinner/timer state on backend error
            }

        } catch (error) {
            console.error('Error submitting form:', error);
            outputDiv.textContent = 'An error occurred while submitting the form.';
            stopTimer(); // Stop timer on fetch error
            displayTotalDuration(); // Display duration on fetch error
            resetProcessStatus(); // Reset button/spinner/timer state on fetch error
        }
    });

    // --- Server-Sent Events (SSE) for Real-time Output ---
    function streamOutput() {
        const eventSource = new EventSource('/stream_output');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'output') {
                outputDiv.textContent += data.content;
                // Auto-scroll to the bottom
                outputDiv.scrollTop = outputDiv.scrollHeight;
            } else if (data.type === 'complete') {
                outputDiv.textContent += "\n--- Process Complete ---\n";
                resultsDiv.style.display = 'block';
                reportLinksDiv.innerHTML = ''; // Clear previous links
                if (data.report_files && data.report_files.length > 0) {
                    data.report_files.forEach(file => {
                        const link = document.createElement('a');
                        // Assuming files are served from /reports/
                        link.href = `/reports/${file.split('/').pop()}`; // Use filename only for the URL
                        link.textContent = `Download ${file.split('/').pop()}`;
                        link.target = '_blank'; // Open in new tab
                        reportLinksDiv.appendChild(link);
                        reportLinksDiv.appendChild(document.createElement('br'));
                    });
                } else {
                    reportLinksDiv.textContent = "No report files found.";
                }
                eventSource.close(); // Close the connection when complete
                stopTimer(); // Stop the timer on completion
                displayTotalDuration(); // Display total duration
                resetProcessStatus(); // Reset button/spinner/timer state
            } else if (data.type === 'error') {
                 outputDiv.textContent += `\n--- Error: ${data.content} ---\n`;
                 stopTimer(); // Stop the timer on error
                 displayTotalDuration(); // Display total duration
                 resetProcessStatus(); // Reset button/spinner/timer state
            }
        };

        eventSource.onerror = function(event) {
            console.error('SSE Error:', event);
            outputDiv.textContent += '\n--- Connection to output stream closed. ---\n';
            eventSource.close();
            stopTimer(); // Stop the timer on SSE error
            displayTotalDuration(); // Display total duration
            resetProcessStatus(); // Reset button/spinner/timer state
        };
    }

    // --- Timer Logic ---
    let timerInterval;
    let startTime;
    let totalDuration = 0;

    function startTimer() {
        startTime = Date.now();
        timerSpan.textContent = '00:00:00';
        timerInterval = setInterval(updateTimer, 1000);
    }

    function updateTimer() {
        const elapsed = Date.now() - startTime;
        const seconds = Math.floor(elapsed / 1000);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainingSeconds = seconds % 60;

        const formattedTime = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
        timerSpan.textContent = formattedTime;
        totalDuration = seconds; // Store total duration in seconds
    }

    function stopTimer() {
        clearInterval(timerInterval);
    }

    function displayTotalDuration() {
        const hours = Math.floor(totalDuration / 3600);
        const minutes = Math.floor((totalDuration % 3600) / 60);
        const seconds = totalDuration % 60;
        const formattedDuration = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        outputDiv.textContent += `\nTotal Duration: ${formattedDuration}\n`;
    }

    function resetProcessStatus() {
        generateButton.disabled = false;
        processStatusDiv.style.display = 'none';
        stopButton.disabled = false; // Reset disabled state
        stopButton.textContent = 'Stop Report'; // Reset text
        timerSpan.textContent = '00:00:00'; // Reset timer display
        totalDuration = 0; // Reset total duration
    }


    // --- Handle Stop Button Click ---
    stopButton.addEventListener('click', async function() {
        // Disable stop button while sending stop request
        stopButton.disabled = true;
        stopButton.textContent = 'Stopping...';
        stopTimer(); // Stop the timer immediately on click

        try {
            const response = await fetch('/stop_report', {
                method: 'POST'
            });
            const result = await response.json();
            outputDiv.textContent += `\n--- ${result.message} ---\n`;
        } catch (error) {
            console.error('Error sending stop signal:', error);
            outputDiv.textContent += '\n--- Error sending stop signal. ---\n';
        } finally {
            resetProcessStatus(); // Reset button/spinner/timer state
        }
    });

});