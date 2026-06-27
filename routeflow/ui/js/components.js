/* Reusable UI Components and Rendering Helpers
   Provides dependency-free toast alerts, modals, loaders, paginators, and pure SVG charting.
*/

// ===========================================================================
// 1. Toast Notifications
// ===========================================================================
export const Toast = {
    show(title, message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        toast.innerHTML = `
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">&times;</button>
        `;
        
        container.appendChild(toast);
        
        // Setup dismiss
        const closeBtn = toast.querySelector('.toast-close');
        const dismiss = () => {
            toast.style.animation = 'slideIn 0.2s ease-out reverse';
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 200);
        };
        
        closeBtn.addEventListener('click', dismiss);
        
        if (duration > 0) {
            setTimeout(dismiss, duration);
        }
    },
    
    success(title, message) {
        this.show(title, message, 'success');
    },
    
    warning(title, message) {
        this.show(title, message, 'warning');
    },
    
    error(title, message) {
        this.show(title, message, 'error', 6000);
    }
};

// ===========================================================================
// 2. Modals and Confirmation Dialogs
// ===========================================================================
export const Modal = {
    show(title, contentHtml, onOpen = null) {
        const container = document.getElementById('modal-container');
        const titleEl = document.getElementById('modal-title');
        const bodyEl = document.getElementById('modal-body');
        const closeBtn = document.getElementById('modal-close');
        
        if (!container || !titleEl || !bodyEl) return;
        
        titleEl.textContent = title;
        bodyEl.innerHTML = contentHtml;
        
        // Remove hidden class
        container.classList.remove('hidden');
        
        const close = () => {
            container.classList.add('hidden');
            bodyEl.innerHTML = '';
        };
        
        closeBtn.onclick = close;
        
        // Click outside to close
        container.onclick = (e) => {
            if (e.target === container) {
                close();
            }
        };
        
        if (onOpen) {
            onOpen(bodyEl, close);
        }
    },
    
    confirm(title, message, onConfirm, confirmText = 'Confirm', type = 'info') {
        const btnClass = type === 'danger' ? 'btn-danger' : 'btn-primary';
        const html = `
            <div style="margin-bottom: 24px; font-size: 14px; color: #B8B8B8;">${message}</div>
            <div style="display: flex; justify-content: flex-end; gap: 12px;">
                <button id="modal-cancel-btn" class="btn btn-secondary">Cancel</button>
                <button id="modal-confirm-btn" class="btn ${btnClass}">${confirmText}</button>
            </div>
        `;
        
        this.show(title, html, (body, close) => {
            const cancelBtn = body.querySelector('#modal-cancel-btn');
            const confirmBtn = body.querySelector('#modal-confirm-btn');
            
            cancelBtn.onclick = close;
            confirmBtn.onclick = async () => {
                confirmBtn.disabled = true;
                confirmBtn.innerHTML = '<span class="spinner"></span>';
                try {
                    await onConfirm();
                    close();
                } catch (err) {
                    Toast.error('Action Failed', err.message);
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = confirmText;
                }
            };
        });
    }
};

// ===========================================================================
// 3. Loaders and Empty States
// ===========================================================================
export const Loader = {
    renderSpinner() {
        return `<div style="display: flex; justify-content: center; align-items: center; padding: 40px 0; width: 100%;">
            <span class="spinner" style="width: 32px; height: 32px; border-width: 3px;"></span>
        </div>`;
    },
    
    renderSkeletonTable(rows = 5, cols = 4) {
        let rowsHtml = '';
        for (let r = 0; r < rows; r++) {
            rowsHtml += '<tr>';
            for (let c = 0; c < cols; c++) {
                rowsHtml += `<td><div class="skeleton skeleton-text" style="width: ${30 + Math.random() * 60}%;"></div></td>`;
            }
            rowsHtml += '</tr>';
        }
        return `
            <table class="table">
                <thead>
                    <tr>
                        ${Array(cols).fill(0).map(() => '<th><div class="skeleton skeleton-text" style="width: 40px;"></div></th>').join('')}
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        `;
    },
    
    renderSkeletonCards(count = 3) {
        let cardsHtml = '';
        for (let i = 0; i < count; i++) {
            cardsHtml += `
                <div class="card">
                    <div class="skeleton skeleton-title"></div>
                    <div class="skeleton skeleton-text" style="width: 80%;"></div>
                    <div class="skeleton skeleton-text" style="width: 60%;"></div>
                    <div class="skeleton skeleton-text" style="width: 70%;"></div>
                </div>
            `;
        }
        return cardsHtml;
    }
};

export const EmptyState = {
    render(title, message, icon = null) {
        let iconHtml = icon;
        if (!iconHtml || iconHtml === '📭' || iconHtml === '🔌' || iconHtml === '🗺️' || iconHtml === '⚠️' || iconHtml === '📝' || iconHtml === '👍') {
            if (iconHtml === '⚠️') {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--error-red, #EF4444)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 16px;">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                `;
            } else if (iconHtml === '🔌') {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--text-muted, #666)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 16px;">
                        <rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect>
                        <rect x="9" y="9" width="6" height="6"></rect>
                        <line x1="9" y1="1" x2="9" y2="4"></line>
                        <line x1="15" y1="1" x2="15" y2="4"></line>
                        <line x1="9" y1="20" x2="9" y2="23"></line>
                        <line x1="15" y1="20" x2="15" y2="23"></line>
                    </svg>
                `;
            } else if (iconHtml === '🗺️') {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--text-muted, #666)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 16px;">
                        <polygon points="3 6 9 3 15 6 21 3 21 18 15 15 9 18 3 15"></polygon>
                        <line x1="9" y1="3" x2="9" y2="18"></line>
                        <line x1="15" y1="6" x2="15" y2="21"></line>
                    </svg>
                `;
            } else if (iconHtml === '📝') {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--text-muted, #666)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.6; margin-bottom: 16px;">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                    </svg>
                `;
            } else if (iconHtml === '👍') {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--success-green, #10B981)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 16px;">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                        <polyline points="9 11 11 13 15 9"></polyline>
                    </svg>
                `;
            } else {
                iconHtml = `
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-muted, #666); opacity: 0.6; margin-bottom: 16px;">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                        <line x1="12" y1="22.08" x2="12" y2="12"></line>
                    </svg>
                `;
            }
        }
        return `
            <div class="empty-state">
                <div class="empty-state-icon">${iconHtml}</div>
                <h3>${title}</h3>
                <p>${message}</p>
            </div>
        `;
    }
};

// ===========================================================================
// 4. Pagination Helper Component
// ===========================================================================
export function renderPagination(offset, limit, currentCount, onPageChange) {
    const currentPage = Math.floor(offset / limit) + 1;
    const hasNext = currentCount >= limit;
    
    const wrapper = document.createElement('div');
    wrapper.className = 'table-pagination';
    
    wrapper.innerHTML = `
        <span class="pagination-text">Page ${currentPage}</span>
        <div class="pagination-controls">
            <button id="prev-page-btn" class="btn btn-secondary btn-sm" ${offset === 0 ? 'disabled' : ''}><svg class="btn-icon" style="margin-right: 4px; margin-left: 0;" viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"></polyline></svg> Previous</button>
            <button id="next-page-btn" class="btn btn-secondary btn-sm" ${!hasNext ? 'disabled' : ''}>Next <svg class="btn-icon" style="margin-left: 4px; margin-right: 0;" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"></polyline></svg></button>
        </div>
    `;
    
    const prevBtn = wrapper.querySelector('#prev-page-btn');
    const nextBtn = wrapper.querySelector('#next-page-btn');
    
    if (offset > 0) {
        prevBtn.onclick = () => onPageChange(offset - limit);
    }
    if (hasNext) {
        nextBtn.onclick = () => onPageChange(offset + limit);
    }
    
    return wrapper;
}

// ===========================================================================
// 5. SVG Chart Generators (Pure JavaScript & SVG, 100% Dependency Free)
// ===========================================================================
export const ChartRenderer = {
    
    /**
     * Renders a Line Chart for time series data (e.g. daily requests / tokens)
     */
    renderLineChart(containerEl, data, xKey, yKey, label = 'Requests') {
        if (!containerEl) return;
        if (!data || data.length === 0) {
            containerEl.innerHTML = EmptyState.render('No Chart Data Available', 'Usage logs do not contain entries for the selected range.');
            return;
        }
        
        // Reverse to ensure chronological order (left-to-right)
        const sortedData = [...data].reverse();
        
        const width = 600;
        const height = 260;
        const padding = { top: 20, right: 30, bottom: 40, left: 50 };
        
        const yValues = sortedData.map(d => Number(d[yKey]));
        const maxY = Math.max(...yValues, 5); // Minimum peak of 5 to scale nicely
        const minY = 0;
        
        const getX = (index) => padding.left + (index / (sortedData.length - 1)) * (width - padding.left - padding.right);
        const getY = (value) => height - padding.bottom - ((value - minY) / (maxY - minY)) * (height - padding.top - padding.bottom);
        
        // Draw gridlines
        let gridLines = '';
        const ticks = 4;
        for (let i = 0; i <= ticks; i++) {
            const val = minY + (i / ticks) * (maxY - minY);
            const y = getY(val);
            gridLines += `
                <line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" class="chart-grid"></line>
                <text x="${padding.left - 10}" y="${y + 4}" text-anchor="end" class="chart-label">${Math.round(val)}</text>
            `;
        }
        
        // Draw X Axis dates
        let xLabels = '';
        const labelInterval = Math.max(1, Math.floor(sortedData.length / 5));
        sortedData.forEach((d, i) => {
            if (i % labelInterval === 0 || i === sortedData.length - 1) {
                const x = getX(i);
                // Formatting day (e.g. 2026-06-25 -> 06-25)
                const dateParts = d[xKey].split('-');
                const labelStr = dateParts.length >= 3 ? `${dateParts[1]}/${dateParts[2]}` : d[xKey];
                
                xLabels += `
                    <text x="${x}" y="${height - padding.bottom + 20}" text-anchor="middle" class="chart-label">${labelStr}</text>
                `;
            }
        });
        
        // Generate path coordinates
        let points = '';
        let areaPoints = `M ${getX(0)} ${height - padding.bottom}`;
        
        sortedData.forEach((d, i) => {
            const x = getX(i);
            const y = getY(Number(d[yKey]));
            points += `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
            areaPoints += ` L ${x} ${y}`;
        });
        
        areaPoints += ` L ${getX(sortedData.length - 1)} ${height - padding.bottom} Z`;
        
        // Generate circles on hover
        let circles = '';
        sortedData.forEach((d, i) => {
            const x = getX(i);
            const y = getY(Number(d[yKey]));
            circles += `
                <circle cx="${x}" cy="${y}" r="4" fill="#0A0A0A" stroke="#FF7A00" stroke-width="2">
                    <title>${d[xKey]}: ${d[yKey]} ${label}</title>
                </circle>
            `;
        });
        
        containerEl.innerHTML = `
            <div class="chart-container">
                <svg viewBox="0 0 ${width} ${height}" class="svg-chart">
                    <defs>
                        <linearGradient id="orange-gradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="#FF7A00" stop-opacity="0.3"/>
                            <stop offset="100%" stop-color="#FF7A00" stop-opacity="0"/>
                        </linearGradient>
                    </defs>
                    
                    <!-- Grid -->
                    ${gridLines}
                    
                    <!-- Area Under Curve -->
                    <path d="${areaPoints}" class="chart-area"></path>
                    
                    <!-- Line -->
                    <path d="${points}" class="chart-line"></path>
                    
                    <!-- Labels -->
                    ${xLabels}
                    
                    <!-- Plot Dots -->
                    ${circles}
                </svg>
            </div>
        `;
    },
    
    /**
     * Renders a Bar Chart for provider or model allocations
     */
    renderBarChart(containerEl, data, labelKey, valueKey, valueSuffix = '') {
        if (!containerEl) return;
        if (!data || data.length === 0) {
            containerEl.innerHTML = EmptyState.render('No Data Available', 'Usage metrics do not contain logs for this chart.');
            return;
        }
        
        const width = 600;
        const height = 260;
        const padding = { top: 20, right: 30, bottom: 40, left: 80 };
        
        const maxVal = Math.max(...data.map(d => Number(d[valueKey])), 1);
        const barHeight = 24;
        const gap = 16;
        
        let barsHtml = '';
        data.slice(0, 5).forEach((d, i) => {
            const val = Number(d[valueKey]);
            const y = padding.top + i * (barHeight + gap);
            const w = ((width - padding.left - padding.right) * val) / maxVal;
            
            barsHtml += `
                <!-- Category Label -->
                <text x="${padding.left - 10}" y="${y + barHeight / 2 + 4}" text-anchor="end" class="chart-label" font-weight="600">${d[labelKey]}</text>
                
                <!-- Background track bar -->
                <rect x="${padding.left}" y="${y}" width="${width - padding.left - padding.right}" height="${barHeight}" fill="#141414" rx="4"></rect>
                
                <!-- Value bar -->
                <rect x="${padding.left}" y="${y}" width="${Math.max(4, w)}" height="${barHeight}" class="chart-bar">
                    <title>${d[labelKey]}: ${val}${valueSuffix}</title>
                </rect>
                
                <!-- Inner value text -->
                <text x="${padding.left + Math.max(4, w) + 8}" y="${y + barHeight / 2 + 4}" class="chart-label" fill="#FFFFFF">${val.toLocaleString()}${valueSuffix}</text>
            `;
        });
        
        containerEl.innerHTML = `
            <div class="chart-container">
                <svg viewBox="0 0 ${width} ${height}" class="svg-chart">
                    ${barsHtml}
                </svg>
            </div>
        `;
    },
    
    /**
     * Renders a Donut Chart for model distribution
     */
    renderDonutChart(containerEl, data, labelKey, valueKey, valueSuffix = '') {
        if (!containerEl) return;
        if (!data || data.length === 0) {
            containerEl.innerHTML = EmptyState.render('No Data Available', 'Usage metrics do not contain logs for this chart.');
            return;
        }
        
        const width = 360;
        const height = 260;
        const radius = 60;
        const cx = 130;
        const cy = 130;
        const circumference = 2 * Math.PI * radius;
        
        const total = data.reduce((sum, d) => sum + Number(d[valueKey]), 0);
        
        // Selected distinct theme-aligned colors (HSL tailored colors)
        const colors = [
            '#FF7A00', // Primary Accent Orange
            '#FF922B', // Hover Accent Orange
            '#FACC15', // Amber
            '#22C55E', // Success Green
            '#60A5FA', // Info Blue
            '#EF4444', // Error Red
            '#666666'  // Slate Gray
        ];
        
        let accumulatedPercent = 0;
        let segmentsHtml = '';
        let legendsHtml = '';
        
        data.forEach((d, i) => {
            const val = Number(d[valueKey]);
            const pct = val / total;
            const strokeDash = pct * circumference;
            const strokeOffset = circumference - (accumulatedPercent * circumference);
            const color = colors[i % colors.length];
            
            segmentsHtml += `
                <circle cx="${cx}" cy="${cy}" r="${radius}" 
                        class="chart-donut-segment" 
                        stroke="${color}" 
                        stroke-dasharray="${strokeDash} ${circumference - strokeDash}" 
                        stroke-dashoffset="${strokeOffset}" 
                        transform="rotate(-90 ${cx} ${cy})">
                    <title>${d[labelKey]}: ${val.toLocaleString()}${valueSuffix} (${Math.round(pct * 100)}%)</title>
                </circle>
            `;
            
            legendsHtml += `
                <div class="legend-item">
                    <span class="legend-color" style="background-color: ${color};"></span>
                    <span>${d[labelKey]} (${Math.round(pct * 100)}%)</span>
                </div>
            `;
            
            accumulatedPercent += pct;
        });
        
        containerEl.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-around; width: 100%; height: 100%; flex-wrap: wrap;">
                <div class="chart-container" style="max-width: 240px; height: 240px;">
                    <svg viewBox="0 0 ${width} ${height}" class="svg-chart">
                        <!-- Center background circle to make it look clean -->
                        <circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="#1A1A1A" stroke-width="24"></circle>
                        
                        <!-- Segments -->
                        ${segmentsHtml}
                        
                        <!-- Inner text -->
                        <text x="${cx}" y="${cy - 4}" text-anchor="middle" class="chart-label" fill="#B8B8B8" font-size="11px">TOTAL</text>
                        <text x="${cx}" y="${cy + 14}" text-anchor="middle" class="chart-label" fill="#FFFFFF" font-size="16px" font-weight="700">${total.toLocaleString()}</text>
                    </svg>
                </div>
                <div class="chart-legend" style="flex: 1; min-width: 160px; flex-direction: column; align-items: flex-start; justify-content: center; gap: 8px;">
                    ${legendsHtml}
                </div>
            </div>
        `;
    }
};
