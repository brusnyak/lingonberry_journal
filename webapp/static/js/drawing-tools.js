// TradingView-style Drawing Tools for Charts
class DrawingTools {
    constructor(canvas, chart) {
        this.canvas = canvas;
        this.chart = chart;
        this.ctx = canvas.getContext('2d');
        this.drawings = [];
        this.currentTool = null;
        this.isDrawing = false;
        this.startPoint = null;
        this.tempDrawing = null;

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.onMouseLeave.bind(this));
    }

    setTool(tool) {
        this.currentTool = tool;
        this.canvas.style.cursor = tool ? 'crosshair' : 'default';
    }

    getChartCoordinates(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Convert canvas coordinates to chart data coordinates
        const chartArea = this.chart.chartArea;
        if (!chartArea) return null;

        const xScale = this.chart.scales.x;
        const yScale = this.chart.scales.y;

        if (!xScale || !yScale) return null;

        // Get data index from x position
        const dataIndex = Math.round(xScale.getValueForPixel(x));
        const value = yScale.getValueForPixel(y);

        return { x, y, dataIndex, value };
    }

    onMouseDown(event) {
        if (!this.currentTool) return;

        const coords = this.getChartCoordinates(event);
        if (!coords) return;

        this.isDrawing = true;
        this.startPoint = coords;
    }

    onMouseMove(event) {
        if (!this.isDrawing || !this.startPoint) return;

        const coords = this.getChartCoordinates(event);
        if (!coords) return;

        // Update temporary drawing
        this.tempDrawing = {
            type: this.currentTool,
            start: this.startPoint,
            end: coords,
            color: '#ff8c00',
            width: 2
        };

        this.redraw();
    }

    onMouseUp(event) {
        if (!this.isDrawing || !this.startPoint) return;

        const coords = this.getChartCoordinates(event);
        if (!coords) return;

        // Save the drawing
        const drawing = {
            type: this.currentTool,
            start: this.startPoint,
            end: coords,
            color: '#ff8c00',
            width: 2,
            id: Date.now()
        };

        this.drawings.push(drawing);
        this.tempDrawing = null;
        this.isDrawing = false;
        this.startPoint = null;

        this.redraw();
    }

    onMouseLeave() {
        if (this.isDrawing) {
            this.isDrawing = false;
            this.startPoint = null;
            this.tempDrawing = null;
            this.redraw();
        }
    }

    drawLine(drawing) {
        this.ctx.beginPath();
        this.ctx.strokeStyle = drawing.color;
        this.ctx.lineWidth = drawing.width;
        this.ctx.moveTo(drawing.start.x, drawing.start.y);
        this.ctx.lineTo(drawing.end.x, drawing.end.y);
        this.ctx.stroke();
    }

    drawRectangle(drawing) {
        this.ctx.strokeStyle = drawing.color;
        this.ctx.lineWidth = drawing.width;
        this.ctx.fillStyle = drawing.color + '20'; // 20% opacity

        const x = Math.min(drawing.start.x, drawing.end.x);
        const y = Math.min(drawing.start.y, drawing.end.y);
        const width = Math.abs(drawing.end.x - drawing.start.x);
        const height = Math.abs(drawing.end.y - drawing.start.y);

        this.ctx.fillRect(x, y, width, height);
        this.ctx.strokeRect(x, y, width, height);
    }

    drawHorizontalLine(drawing) {
        const chartArea = this.chart.chartArea;
        this.ctx.beginPath();
        this.ctx.strokeStyle = drawing.color;
        this.ctx.lineWidth = drawing.width;
        this.ctx.setLineDash([5, 5]);
        this.ctx.moveTo(chartArea.left, drawing.start.y);
        this.ctx.lineTo(chartArea.right, drawing.start.y);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Draw price label
        const yScale = this.chart.scales.y;
        const price = yScale.getValueForPixel(drawing.start.y);
        this.ctx.fillStyle = drawing.color;
        this.ctx.fillRect(chartArea.right - 60, drawing.start.y - 10, 55, 20);
        this.ctx.fillStyle = '#000';
        this.ctx.font = '11px monospace';
        this.ctx.fillText(price.toFixed(5), chartArea.right - 55, drawing.start.y + 4);
    }

    redraw() {
        // Clear previous drawings
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Redraw all saved drawings
        this.drawings.forEach(drawing => {
            this.drawShape(drawing);
        });

        // Draw temporary drawing
        if (this.tempDrawing) {
            this.drawShape(this.tempDrawing);
        }
    }

    drawShape(drawing) {
        switch (drawing.type) {
            case 'line':
                this.drawLine(drawing);
                break;
            case 'rect':
                this.drawRectangle(drawing);
                break;
            case 'horizontal':
                this.drawHorizontalLine(drawing);
                break;
        }
    }

    clearAll() {
        this.drawings = [];
        this.tempDrawing = null;
        this.redraw();
    }

    removeLastDrawing() {
        this.drawings.pop();
        this.redraw();
    }

    exportDrawings() {
        return JSON.stringify(this.drawings);
    }

    importDrawings(data) {
        try {
            this.drawings = JSON.parse(data);
            this.redraw();
        } catch (e) {
            console.error('Failed to import drawings:', e);
        }
    }
}
