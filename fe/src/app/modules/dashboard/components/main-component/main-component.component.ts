import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { DashboardMainServiceService } from '../../services/dashboard-main-service.service';
import { DashBoardData, Status } from '../../models';
import { catchError } from 'rxjs/internal/operators/catchError';
import { of } from 'rxjs';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-main-component',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './main-component.component.html',
  styleUrls: ['./main-component.component.css']
})

export class MainComponentComponent implements OnInit {

  dashBoardService = inject(DashboardMainServiceService);
  router = inject(Router);
  allData = signal<DashBoardData[]>([]);
  searchTerm = signal<string>('');

  filteredData = computed(() => {
    const searchLower = this.searchTerm().toLowerCase();
    if (!searchLower) return this.allData();

    return this.allData().filter(item =>
      item.meter_data.name.toLowerCase().includes(searchLower)
    );
  });

  ngOnInit() {
    this.dashBoardService.getDataApi().pipe(
      catchError((err) => {
        console.error('Error fetching data', err);
        return this.dashBoardService.getMockData();
      })
    ).subscribe((data) => {
      this.allData.set(data);
    });
  }

  onSearchChange(event: any) {
    this.searchTerm.set(event.target.value);
  }

  getStatusText(status: number): string {
    switch (status) {
      case Status.NORMAL:
        return 'Bình thường';
      case Status.ANOMALY:
        return 'Rò Rỉ';
      case Status.LOST_CONNECTION:
        return 'Mất kết nối';
      default:
        return 'Không xác định';
    }
  }

  getStatusClass(status: number): string {
    switch (status) {
      case Status.NORMAL:
        return 'status-normal';
      case Status.ANOMALY:
        return 'status-anomaly';
      case Status.LOST_CONNECTION:
        return 'status-lost';
      default:
        return 'status-unknown';
    }
  }

  trackByFn(index: number, item: DashBoardData): number {
    return item.id;
  }

  navigateToDetail(item: DashBoardData) {
    this.router.navigate(['/detail', item.meter_data.id, item.meter_data.name]);
  }
}
