import pandas as pd
import numpy as np
from datetime import datetime, timedelta

df = pd.read_csv('measurements.csv')
print(f"Current data: {len(df)} records")

last_records = df.groupby('meter_id').tail(1)
print(last_records[['id', 'meter_id', 'measurement_time']])

new_data = []
current_id = df['id'].max() + 1

for _, last_record in last_records.iterrows():
    meter_id = last_record['meter_id']
    last_time = datetime.fromisoformat(last_record['measurement_time'])
    last_flow = last_record['instant_flow']
    
    for i in range(1, 51):
        new_time = last_time + timedelta(hours=i)
        
        hour = new_time.hour
        if 6 <= hour <= 8:  
            base_flow = last_flow + np.random.normal(15, 5)
        elif 18 <= hour <= 20:    
            base_flow = last_flow + np.random.normal(10, 5)
        elif 22 <= hour or hour <= 5:
            base_flow = last_flow + np.random.normal(-20, 5)
        else: 
            base_flow = last_flow + np.random.normal(0, 8)
            
        flow = max(50, base_flow)
        
        if np.random.random() < 0.02: 
            flow = flow * np.random.uniform(1.5, 2.0) 
            
        pressure = np.random.uniform(2.0, 3.0)
        
        new_data.append({
            'id': current_id,
            'meter_id': meter_id,
            'instant_flow': round(flow, 1),
            'measurement_time': new_time.isoformat(),
            'instant_pressure': round(pressure, 1)
        })
        current_id += 1


new_df = pd.DataFrame(new_data)
print(f"Generated {len(new_df)} new records")

combined_df = pd.concat([df, new_df], ignore_index=True)
combined_df = combined_df.sort_values(['meter_id', 'measurement_time'])

print(f"Total records: {len(combined_df)}")
print("Records per meter:")
print(combined_df.groupby('meter_id').size())

combined_df.to_csv('measurements_extended.csv', index=False)
print("Saved to measurements_extended.csv")
