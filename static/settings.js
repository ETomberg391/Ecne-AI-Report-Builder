document.addEventListener('DOMContentLoaded', function() {
    // --- General Settings Elements ---
    const apiKeyForm = document.getElementById('api-keys-form');
    const llmSettingsForm = document.getElementById('llm-settings-form');
    const llmModelSelect = document.getElementById('llm-model-select');
    const llmModelDetails = document.getElementById('llm-model-details');
    const newLlmModelDetails = document.getElementById('new-llm-model-details');
    const deleteLlmModelButton = document.getElementById('delete-llm-model');

    // --- ChromeDriver Update Elements ---
    const updateButton = document.getElementById('update-chromedriver-btn');
    const modal = document.getElementById('chromedriver-update-modal');
    const outputElement = document.getElementById('chromedriver-update-output');
    const closeButton = modal.querySelector('.close-button');

    // Store loaded LLM settings to avoid re-fetching
    let currentLlmSettingsData = {};

    // --- Load All Settings on Page Load ---
    async function loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();

            // Populate API Keys form
            if (data.api_keys) {
                document.getElementById('google_api_key').value = data.api_keys.GOOGLE_API_KEY || '';
                document.getElementById('google_cse_id').value = data.api_keys.GOOGLE_CSE_ID || '';
                document.getElementById('brave_api_key').value = data.api_keys.BRAVE_API_KEY || '';
            }

            // Populate LLM Models dropdown
            if (data.llm_settings) {
                currentLlmSettingsData = data.llm_settings;
                llmModelSelect.innerHTML = '<option value="">-- Select a model --</option>';
                for (const key in data.llm_settings) {
                    const option = document.createElement('option');
                    option.value = key;
                    option.textContent = key;
                    llmModelSelect.appendChild(option);
                }
                const newLlmOption = document.createElement('option');
                newLlmOption.value = 'new-llm';
                newLlmOption.textContent = 'New LLM';
                llmModelSelect.appendChild(newLlmOption);
            }
            llmModelDetails.style.display = 'none';
            newLlmModelDetails.style.display = 'none';
        } catch (error) {
            console.error('Error loading settings:', error);
            alert('Failed to load settings.');
        }
    }

    // --- Handle LLM Model Selection Change ---
    llmModelSelect.addEventListener('change', function() {
        const selectedKey = this.value;
        llmModelDetails.style.display = 'none';
        newLlmModelDetails.style.display = 'none';

        if (selectedKey === 'new-llm') {
            newLlmModelDetails.style.display = 'block';
            newLlmModelDetails.querySelectorAll('input, textarea').forEach(input => input.value = '');
        } else if (selectedKey && currentLlmSettingsData[selectedKey]) {
            llmModelDetails.style.display = 'block';
            const selectedModelSettings = currentLlmSettingsData[selectedKey];
            document.getElementById('llm-model-name').value = selectedModelSettings.model || '';
            document.getElementById('llm-api-endpoint').value = selectedModelSettings.api_endpoint || '';
            document.getElementById('llm-api-key').value = selectedModelSettings.api_key || '';
            document.getElementById('llm-max-tokens').value = selectedModelSettings.max_tokens || '';
            document.getElementById('llm-temperature').value = selectedModelSettings.temperature || '';
            document.getElementById('llm-model-name').setAttribute('readonly', 'true');
        }
    });

    // --- Handle Save API Keys Form Submission ---
    apiKeyForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const apiKeysData = {
            GOOGLE_API_KEY: document.getElementById('google_api_key').value,
            GOOGLE_CSE_ID: document.getElementById('google_cse_id').value,
            BRAVE_API_KEY: document.getElementById('brave_api_key').value,
        };
        try {
            const response = await fetch('/save_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ apiKeys: apiKeysData })
            });
            const result = await response.json();
            alert(result.message);
            if (response.ok) location.reload();
        } catch (error) {
            console.error('Error saving API keys:', error);
            alert('Failed to save API keys.');
        }
    });

    // --- Handle Save LLM Settings Form Submission ---
    llmSettingsForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const selectedKey = llmModelSelect.value;
        let updatedLlmSettings = { ...currentLlmSettingsData };

        if (selectedKey === 'new-llm') {
            const newModelKey = document.getElementById('new-llm-key').value.trim();
            if (!newModelKey) return alert("Please provide a key for the new LLM model.");
            if (updatedLlmSettings.hasOwnProperty(newModelKey)) return alert(`An LLM model with key "${newModelKey}" already exists.`);
            
            updatedLlmSettings[newModelKey] = {
                model: document.getElementById('new-llm-model-name').value,
                api_endpoint: document.getElementById('new-llm-api-endpoint').value,
                api_key: document.getElementById('new-llm-api-key').value,
                max_tokens: parseFloat(document.getElementById('new-llm-max-tokens').value) || null,
                temperature: parseFloat(document.getElementById('new-llm-temperature').value) || null,
            };
        } else if (selectedKey && updatedLlmSettings.hasOwnProperty(selectedKey)) {
            updatedLlmSettings[selectedKey] = {
                model: document.getElementById('llm-model-name').value,
                api_endpoint: document.getElementById('llm-api-endpoint').value,
                api_key: document.getElementById('llm-api-key').value,
                max_tokens: parseFloat(document.getElementById('llm-max-tokens').value) || null,
                temperature: parseFloat(document.getElementById('llm-temperature').value) || null,
            };
        } else {
            return alert("Please select an LLM model to edit or choose 'New LLM'.");
        }

        try {
            const response = await fetch('/save_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ llmSettings: updatedLlmSettings })
            });
            const result = await response.json();
            alert(result.message);
            if (response.ok) location.reload();
        } catch (error) {
            console.error('Error saving LLM settings:', error);
            alert('Failed to save LLM settings.');
        }
    });

    // --- Handle Delete LLM Model Button Click ---
    deleteLlmModelButton.addEventListener('click', async function() {
        const selectedKey = llmModelSelect.value;
        if (!selectedKey || selectedKey === "" || selectedKey === "new-llm") return alert("Please select an existing LLM model to delete.");
        
        if (confirm(`Are you sure you want to delete the LLM model "${selectedKey}"?`)) {
            try {
                let updatedLlmSettings = { ...currentLlmSettingsData };
                if (updatedLlmSettings.hasOwnProperty(selectedKey)) {
                    delete updatedLlmSettings[selectedKey];
                    const response = await fetch('/save_settings', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ llmSettings: updatedLlmSettings })
                    });
                    const result = await response.json();
                    alert(result.message);
                    if (response.ok) {
                        loadSettings();
                        llmModelDetails.style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Error deleting LLM model:', error);
                alert('Failed to delete LLM model.');
            }
        }
    });

    // --- ChromeDriver Update Logic ---
    if (updateButton) {
        updateButton.addEventListener('click', async () => {
            modal.style.display = 'block';
            outputElement.textContent = 'Starting update process...';

            try {
                const response = await fetch('/api/update_chromedriver', { method: 'POST' });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                outputElement.textContent = ''; // Clear initial message

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) {
                        outputElement.textContent += '\n\nProcess finished.';
                        break;
                    }
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep the last, possibly incomplete, line

                    for (const line of lines) {
                        if (line.startsWith('data:')) {
                            const data = line.substring(5).trim();
                            if (data) {
                                outputElement.textContent += data + '\n';
                            }
                        }
                    }
                }
            } catch (error) {
                outputElement.textContent += `\n\nAn error occurred: ${error}`;
            }
        });
    }

    if (closeButton) {
        closeButton.addEventListener('click', () => modal.style.display = 'none');
    }

    window.addEventListener('click', (event) => {
        if (event.target == modal) modal.style.display = 'none';
    });

    // --- Initial Load ---
    loadSettings();
});