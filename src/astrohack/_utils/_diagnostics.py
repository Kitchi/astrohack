import numpy as np

from astropy.time import Time

def _calc_index(n, m):
    if n >= m:
        return n % m
    else:
        return n

def _extract_indicies(l, m, squared_radius):
    indicies = []

    assert l.shape[0] == m.shape[0], "l, m must be same size."

    for i in range(l.shape[0]):
        squared_sum = np.power(l[i], 2) + np.power(m[i], 2)
        if squared_sum <= squared_radius:
            indicies.append(i)
            
    return np.array(indicies)

def _the_matplotlib_inspection_function(data, delta=0.01, pol='RR', width=1000, height=450):
  import matplotlib.pyplot as plt

  pixels = 1/plt.rcParams['figure.dpi']
  plt.rcParams['figure.figsize'] = [width*pixels, height*pixels]
    
  UNIX_CONVERSION = 3506716800
    
  radius = np.power(data.grid_parms['cell_size']*delta, 2)
  pol_index = np.squeeze(np.where(data.pol.values==pol))
    
  l = data.DIRECTIONAL_COSINES.values[..., 0] 
  m = data.DIRECTIONAL_COSINES.values[..., 1]
    
  assert l.shape[0] == m.shape[0], "l, m dimensions don't match!"
    
  indicies = _extract_indicies(
        l = l, 
        m = m, 
        squared_radius=radius
  )
    
  vis = data.isel(time=indicies).VIS
  times = Time(vis.time.data - UNIX_CONVERSION, format='unix').iso
    
  fig, axis = plt.subplots(2, 1)
    
  chan = np.arange(0, data.chan.data.shape[0])
    
  for i in range(times.shape[0]):
    
        axis[0].plot(chan, vis[i, :, pol_index].real, marker='o', label=times[i])
        axis[0].set_title('Calibration Check: polarization={p}'.format(p=data.pol.values[pol_index]))
        axis[0].set_ylabel("Visibilities (real)")
        axis[0].set_xlabel("Channel")
    
        axis[0].legend()
    
        axis[1].plot(chan, vis[i, :, pol_index].imag, marker='o', label=times[i])
        axis[1].set_ylabel("Visibilities (imag)")
        axis[1].set_xlabel("Channel")
        
        axis[1].legend()    
    
def _the_plotly_inspection_function(data, delta=0.01, pol='RR', width=1000, height=450):
    import plotly.graph_objects as go
    import plotly.express as px
    
    from plotly.subplots import make_subplots
    
    UNIX_CONVERSION = 3506716800
    
    pol_index = np.squeeze(np.where(data.pol.values==pol))
    radius = np.power(data.grid_parms['cell_size']*delta, 2)
    
    l = data.DIRECTIONAL_COSINES.values[..., 0] 
    m = data.DIRECTIONAL_COSINES.values[..., 1]
    
    assert l.shape[0] == m.shape[0], "l, m dimensions don't match!"
    
    indicies = _extract_indicies(
        l = l, 
        m = m, 
        squared_radius=radius
    )
    
    vis = data.isel(time=indicies).VIS
    times = Time(vis.time.data - UNIX_CONVERSION, format='unix').iso
    
    chan = np.arange(0, data.chan.data.shape[0])
    fig = make_subplots(rows=2, cols=1, start_cell="top-left")
    
    for i in range(times.shape[0]):
        index = _calc_index(i, 10)
        fig.add_trace(
            go.Scatter(
                x=chan, 
                y=vis[i, :, pol_index].real,
                marker={
                    'color': px.colors.qualitative.D3[index],
                    'line': {
                        'width': 3,
                        'color': px.colors.qualitative.D3[index]
                    }
                },
                mode='lines+markers',
                name=times[i],
                legendgroup=times[i],
                meta=[times[i]],
                hovertemplate="<br>".join([
                    '<b>time: %{meta[0]}</b><extra></extra>', 
                    'chan:%{x}', 
                    'vis: %{y}'
                ])
            ), row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=chan, 
                y=vis[i, :, pol_index].imag,
                marker={
                    'color': px.colors.qualitative.D3[index],
                    'line': {
                        'width': 3,
                        'color': px.colors.qualitative.D3[index]
                    }
                },
                mode='lines+markers',
                name=times[i],
                legendgroup=times[i],
                showlegend=False,
                meta=[times[i]],
                hovertemplate="<br>".join([
                    '<b>time: %{meta[0]}</b><extra></extra>', 
                    'chan:%{x}', 
                    'vis: %{y}'
                ])
            ), row=2, col=1
        )
        
        fig['layout']={
            'height':height,
            'width': width,
            'title': 'Calibration Check: polarization={p}'.format(p=data.pol.values[pol_index]),
            'paper_bgcolor':'#FFFFFF',
            'plot_bgcolor':'#FFFFFF',
            'font_color': '#323130',
            'yaxis':{
                'title':'Visibilities (real)',
                'linecolor':'#626567',
                'linewidth': 2,
                'zeroline':False,
                'mirror': True,
                'showline':True,
                'anchor': 'x', 
                'domain': [0.575, 1.0],
                #'showspikes': True,
                #'spikemode': 'across',
                #'spikesnap': 'cursor',
            },
            'yaxis2':{
                'title':'Visibilities (imag)',
                'linecolor':'#626567',
                'linewidth': 2,
                'zeroline':False,
                'mirror': True,
                'showline':True,
                'anchor': 'x2',
                'domain': [0.0, 0.425]
            },
            'xaxis':{
                'title':'Channel',
                'zeroline':False,
                'linecolor':' #626567',
                'linewidth': 2,
                'mirror': True,
                'showline':True,
                'anchor': 'y', 
                'domain': [0.0, 1.0],
                #'showspikes': True,
                #'spikemode': 'across',
                #'spikesnap': 'cursor',
            },
            'xaxis2':{                
                'title':'Channel',
                'zeroline':False,
                'linecolor':' #626567',
                'linewidth': 2,
                'mirror': True,
                'showline':True,
                'anchor': 'y2', 
                'domain': [0.0, 1.0]
            }
        }
    
    fig.show()