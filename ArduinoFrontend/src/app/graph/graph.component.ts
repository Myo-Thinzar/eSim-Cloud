import { Component, Directive, Input, OnInit, } from '@angular/core';
import { Chart } from 'chart.js';
import { GraphDataService } from '../graph-data.service';
import { Workspace } from '../Libs/Workspace';

@Component({
  selector: 'app-graph',
  templateUrl: './graph.component.html',
  styleUrls: ['./graph.component.css']
})
export class GraphComponent implements OnInit {

  data: number[];
  xlabels: number[];
  pinGraph: Chart;
  chartConfig: any;
  previousTime: Date;
  @Input() id: string;
  @Input() arduinoId: number;
  @Input() arduinoName: string;
  state: boolean;
  nodes: string[];
  ignored: boolean = false;
  pinLabel = "";

  constructor(private graphDataService: GraphDataService) {
    this.data = [];
    this.xlabels = [];
    this.chartConfig = {};
    this.previousTime = new Date();
    this.nodes = [];
  }

  ngOnInit() {
    this.pinLabel = `${this.arduinoName} - D${this.id}`;
    Workspace.simulationStopped.subscribe(res => {
      this.ignored = false;
    });
    Workspace.simulationStarted.subscribe(res => {
      this.clearGraph();
    });
  }

  ngAfterViewInit() {
    const canvasElement = `graph${this.id}`;
    this.configChart();
    this.pinGraph = new Chart(document.getElementById(canvasElement) as HTMLCanvasElement, this.chartConfig);
    GraphDataService.voltageChange.subscribe(res => {
      if(this.arduinoId === res.arduino.id) {
        let pinNumber = 15 - parseInt(this.id, 10);
        this.pinGraph.data.datasets[0].label = res.label;
        this.data.push((res.value >> pinNumber) & 1);
        if(this.xlabels.length === 0) {
          this.xlabels.push(new Date(res.time).getTime() - new Date(res.time).getTime());
          this.previousTime = new Date(res.time);
        }
        this.xlabels.push(new Date(res.time).getTime() - new Date(this.previousTime).getTime());
        this.previousTime = new Date(res.time);
        console.log(this.pinLabel, this.data);
        console.log(this.pinLabel, this.xlabels);
        this.pinGraph.update();
      }
    });
  }

  clearGraph() {
    this.data.splice(0, this.data.length);
    this.xlabels.splice(0, this.xlabels.length);
    this.pinGraph.update();
    // console.log(this.nodes);
  }

  configChart() {
    this.chartConfig = {
      animationEnabled: true,
      type: 'line',
      data: {
        labels: this.xlabels,
        datasets: [{
          label: 'PIN',
          fill: false,
          backgroundColor: 'rgb(0, 0, 0)',
          borderColor: 'rgb(0, 0, 0)',
          data: this.data,
          steppedLine: true,
        }],
      },
      options: {
        legend: {
          display: false
        },
        responsive: true,
        scales: {
          xAxes: [{
            scaleLabel: {
              display: false,
              labelString: 'Time'
            }, gridLines: {
              display: false
            },
            ticks: {
              display: false,
            }
          }],
          yAxes: [{
            scaleLabel: {
              display: false,
              labelString: 'States',
            },
            gridLines: {
              display: false
            },
            ticks: {
              beginAtZero: true,
              min: 0,
              stepSize: 1,
              max: 2,
              callback: function(value, index) {
                return value > 1 ? '': value;
              },
            }
          }],
        },
      },
    }
  }
}