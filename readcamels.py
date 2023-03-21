#-------------------------------------------------------------------------------
# Name:        module4
# Purpose:
#
# Author:      cagon
#
# Created:     10/01/2023
# Copyright:   (c) cagon 2023
# Licence:     <your licence>
#-------------------------------------------------------------------------------

#!pip install torch
#!pip install torch_geometric
#!pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-1.12.0+cu116.html

#import torch.utils.data
import matplotlib.pyplot as plt

import glob
import pandas as pd
import numpy as np
import scipy
import torch
#import torch_geometric
#from torch_geometric.transforms import NormalizeFeatures
#from torch_geometric.data import DataLoader,Data



from pathlib import Path
from typing import List, Tuple
import sys
import pickle as pkl
from sklearn.preprocessing import StandardScaler,MinMaxScaler
from timeit import default_timer
import matplotlib.pyplot as plt
import os

device = 'cuda' if torch.cuda.is_available() else 'cpu'

import os
os.getcwd()

#C:\Users\cagon\OneDrive\Desktop\Columbia\Camels_Jupyter_Download

os.chdir('C:/Users/cagon/OneDrive/Desktop/Columbia/Camels_Jupyter_Download')

rootdir = 'C:/Users/cagon/OneDrive/Desktop/Columbia/Camels_Jupyter_Download'

## Maurer mean/std calculated over all basins in period 10/1/1999 until 09/30/2008
# [note this is not correct]

import numpy as np
SCALER = {
    'input_means': np.array([3.17563234, 372.01003929, 17.31934062, 3.97393362, 924.98004197]),
    'input_stds': np.array([6.94344737, 131.63560881, 10.86689718, 10.3940032, 629.44576432]),
    'output_mean': np.array([1.49996196]),
    'output_std': np.array([3.62443672])
}

# NLDAS mean/std calculated over all basins in period 01.10.1999 until 30.09.2008
#"""
#SCALER = {
    #'input_means': np.array([3.015, 357.68, 10.864, 10.864, 1055.533]),
    #'input_stds': np.array([7.573, 129.878, 10.932, 10.932, 705.998]),
    #'output_mean': np.array([1.49996196]),
    #'output_std': np.array([3.62443672])
#}

def toTensor(nparr, dtype):
    """utility function for tensor conversion
    """
    return torch.tensor(nparr, dtype=dtype)

import pandas as pd
rootdir = 'C:/Users/cagon/OneDrive/Desktop/Columbia/Camels_Jupyter_Download'
def _read_gauge_info(path):
    #modified from
    #https://github.com/kratzert/lstm_for_pub/blob/master/extract_benchmarks.py

    gauge_info = pd.read_csv(path)
    gauge_info.columns=['huc2','gauge_id','gauge_name','lat','lng','drainage_area']

    gauge_info['gauge_str'] = gauge_info['gauge_id']
    gauge_info['gauge_str'] = gauge_info['gauge_str'].apply(lambda x: '{0:0>8}'.format(x))

    gauge_info['gauge_id'] = gauge_info['gauge_id'].apply(pd.to_numeric)
    gauge_info['lat'] = gauge_info['lat'].apply(pd.to_numeric)
    gauge_info['lng'] = gauge_info['lng'].apply(pd.to_numeric)

    return gauge_info

def getStaticAttr():
    """Load static attributes of all 531 basins
    Assume the camels data are in camels
    """
    basinlistfile = f'{rootdir}/basin_list1.txt'
    df_basinset = pd.read_csv(basinlistfile, header=None)
    df_basinset.columns=['gauge_id']

    # --- Metadata and Catchment Characteristics ---------------------------

    # The purpose of loading this metadata file is to get huc and basin IDs for
    # constructing model output file names.
    # we also need the gauge areas for normalizing NWM output.

    # load metadata file (with hucs)
    meta_df = _read_gauge_info(f'{rootdir}/gauge_information.csv')
    assert meta_df['gauge_id'].is_unique  # make sure no basins or IDs are repeated
    # concatenate catchment characteristics with meta data
    meta_df = meta_df.round({
        'lat': 5,
        'lng': 5
    })  # latitudes and longitudes should be to 5 significant digit

    #get subbasins

    meta_df = df_basinset.join(
            meta_df.set_index('gauge_id'),
            on='gauge_id')
    # load characteristics file (with areas)
    rootloc = f'{rootdir}/'  # catchment characteristics file name
    fnames = ['camels_clim.txt','camels_geol.txt','camels_hydro.txt','camels_soil.txt','camels_topo.txt','camels_vege.txt']

    static_df = None
    for afile in fnames:
        fname = '/'.join([rootloc, afile])
        print ('processing', fname)
        char_df = pd.read_table(fname, delimiter=';', dtype={'gauge_id': int})  # read characteristics file

        assert char_df['gauge_id'].is_unique  # make sure no basins or IDs are repeated

        char_df = char_df.round({'gauge_lat': 5, 'gauge_lon': 5})
        #assert meta_df['gauge_id'].equals(
        #    char_df['gauge_id'])  # check catchmenet chars & metdata have the same basins
        #assert meta_df['lat'].equals(char_df['gauge_lat'])  # check that latitudes and longitudes match
        #assert meta_df['lng'].equals(char_df['gauge_lon'])
        if static_df is None:
            static_df = char_df.join(
            meta_df.set_index('gauge_id'),
            on='gauge_id',how='right')  # turn into a single dataframe (only need huc from meta)
        else:
            static_df = char_df.join(
            static_df.set_index('gauge_id'),
            on='gauge_id', how='right')  # turn into a single dataframe (only need huc from meta)

    nBasins = static_df.shape[0]  # count number of basins

    print ('number of basins', nBasins)
    print('static list', static_df)

    return static_df

def getSubSet(allDF):
    """Return a subset of static attribute dataframe
    Reference: Nearing 2019 WRR paper, Table 1
    """

    colnames = ['p_mean', 'pet_mean', 'aridity', 'p_seasonality', 'frac_snow',
        'high_prec_freq', 'high_prec_dur','low_prec_freq', 'low_prec_dur', 'elev_mean',
         'slope_mean', 'area_gages2', 'frac_forest', 'lai_max', 'lai_diff',
         'gvf_max', 'gvf_diff','soil_depth_pelletier', 'soil_depth_statsgo','soil_porosity',
          'soil_conductivity','max_water_content', 'sand_frac', 'silt_frac','clay_frac',
          'geol_permeability', 'carbonate_rocks_frac',
    ]
    return  allDF[colnames]

def getSubSet4Clustering(allDF):
    """Return a subset of static attribute dataframe for clustering
    Reference: Nearing 2019 WRR paper, Table 1
    """

    
    colnames = ['gauge_lat', 'gauge_lon',
        'p_mean', 'pet_mean', 'aridity', 'p_seasonality', 'frac_snow',
        'high_prec_freq', 'high_prec_dur','low_prec_freq', 'low_prec_dur', 'elev_mean',
         'slope_mean', 'area_gages2', 'frac_forest', 'lai_max', 'lai_diff',
         'gvf_max', 'gvf_diff','soil_depth_pelletier', 'soil_depth_statsgo','soil_porosity',
          'soil_conductivity','max_water_content', 'sand_frac', 'silt_frac','clay_frac',
          'geol_permeability', 'carbonate_rocks_frac',
    ]

    return  allDF[colnames]

from pathlib import Path, Path
from typing import List, Tuple
import pandas as pd

def load_forcing(camels_root: Path, forcingType: str, basin: str) -> Tuple[pd.DataFrame, int]:
    """Load Maurer forcing data from text files.
    Parameters
    ----------
    camels_root : PosixPath
        Path to the main directory of the CAMELS data set
    basin : str
        8-digit USGS gauge id
    forcingType: str
        type of forcing data
    Returns
    -------
    df : pd.DataFrame
        DataFrame containing the Maurer forcing
    area: int
        Catchment area (read-out from the header of the forcing file)
    Raises
    ------
    RuntimeError
        If not forcing file was found.
    """
    #    forcing_path = camels_root / 'basin_mean_forcing' / 'maurer_extended'
    #    forcing_path = camels_root / 'basin_mean_forcing' / 'nldas'
    #forcing_path = camels_root / 'basin_mean_forcing' / 'nldas_extended'
    if forcingType=='maurer':
        forcing_path = camels_root / 'maurer'
    elif forcingType=="nldas":
        forcing_path = camels_root / 'nldas_extended'
    else:
        raise RuntimeError("not a valid forcing data type")


    files = list(forcing_path.glob('**/*_forcing_leap.txt'))
    file_path = [f for f in files if f.name[:8] == basin]
    if len(file_path) == 0:
        raise RuntimeError(f'No file for Basin {basin} at {file_path}')
    else:
        file_path = file_path[0]

    df = pd.read_csv(file_path, sep='\s+', header=None, skiprows=4)
    print (file_path)
    #standardize column names
    #note some of the original files have missing column headers
    #e.g., basin_dataset_public_v1p2\basin_mean_forcing\maurer\03\02108000_lump_maurer_forcing_leap.txt02108000
    #

    df.columns = ['Year', 'Mnth', 'Day', 'Hr', 'Dayl(s)', 'PRCP', 'SRAD',
       'SWE', 'Tmax', 'Tmin', 'Vp']
    dates = (df.Year.map(str) + "/" + df.Mnth.map(str) + "/" + df.Day.map(str))
    df.index = pd.to_datetime(dates, format="%Y/%m/%d")

    # load area from header
    with open(file_path, 'r') as fp:
        content = fp.readlines()
        area = int(content[2])

    return df, area

def load_discharge(camels_root: Path, basin: str, area: int) -> pd.Series:
    """[summary]
    Parameters
    ----------
    camels_root : PosixPath
        Path to the main directory of the CAMELS data set
    basin : str
        8-digit USGS gauge id
    area : int
        Catchment area, used to normalize the discharge to mm/day
    Returns
    -------
    pd.Series
        A Series containing the discharge values.
    Raises
    ------
    RuntimeError
        If no discharge file was found.
    """
    discharge_path = camels_root / 'usgs_streamflow'
    files = list(discharge_path.glob('**/*_streamflow_qc.txt'))
    file_path = [f for f in files if f.name[:8] == basin]
    if len(file_path) == 0:
        raise RuntimeError(f'No file for Basin {basin} at {file_path}')
    else:
        file_path = file_path[0]

    col_names = ['basin', 'Year', 'Mnth', 'Day', 'QObs', 'flag']
    df = pd.read_csv(file_path, sep='\s+', header=None, names=col_names)
    #from pathlib import Path  
    #filepath = Path('C:/Users/cagon/OneDrive/Desktop/Columbia/{}.csv'.format(basin))  
    #filepath.parent.mkdir(parents=True, exist_ok=True)  
    #df.to_csv(filepath) 
    dates = (df.Year.map(str) + "/" + df.Mnth.map(str) + "/" + df.Day.map(str))
    df.index = pd.to_datetime(dates, format="%Y/%m/%d")

    # normalize discharge from cubic feed per second to mm per day
    df.QObs = 28316846.592 * df.QObs * 86400 / (area * 10**6)

    return df.QObs

import numpy as np

def normalize_features(feature: np.ndarray, variable: str) -> np.ndarray:
    #https://github.com/kratzert/lstm_for_pub/blob/bb74c3ff3047d2f60a839fa05a4e621587225205/papercode/datautils.py
    """Normalize features using global pre-computed statistics.
    Parameters
    ----------
    feature : np.ndarray
        Data to normalize
    variable : str
        One of ['inputs', 'output'], where `inputs` mean, that the `feature` input are the model
        inputs (meteorological forcing data) and `output` that the `feature` input are discharge
        values.
    Returns
    -------
    np.ndarray
        Normalized features
    Raises
    ------
    RuntimeError
        If `variable` is neither 'inputs' nor 'output'
    """
    if variable == 'inputs':
        feature = (feature - SCALER["input_means"]) / SCALER["input_stds"]
    elif variable == 'output':
        feature = (feature - SCALER["output_mean"]) / SCALER["output_std"]
    else:
        raise RuntimeError(f"Unknown variable type {variable}")
    return feature

def new_normalize_features(feature: np.ndarray, variable: str, scaler: dict) -> np.ndarray:
    """normalize features according to the training period
    [note this should be used instead of the hard-coded scaler]
    Parameters
    ----------
    feature: input/output numpy array
    variable: either "input" or "output
    scaler: the scaler to be used in standard scaling
    Returns
    -------
    feature: scaled feature
    """
    if variable == "inputs":
        feature = (feature - scaler["input_means"]) / scaler["input_stds"]
    elif variable == 'output':
        feature = (feature - scaler["output_mean"]) / scaler["output_std"]
    else:
        raise RuntimeError(f"Unknown variable type {variable}")
    return feature

def genLSTMData(rootfolder, basinList, dates, seq=90, reGen=False, genDF=False, **kwargs):
    """Generate input for graph
    Parameters
    ---------
    rootfolder: posixpath, root of camels dataset
    basinList: string list of all basins
    dates: the start and end dates of training and testing data (note training includes train/val periods)
    seq: lookback period
    reGen, true to regenerate datasets
    genDF: true to reload camels forcing DF
    """
    dir_path = os.path.dirname(os.path.realpath("__file__"))

    #get training and testing dates
    train_start,train_end = dates[0:2]
    test_start,test_end = dates[2:]
    #set default values
    kwargs.setdefault('includeStatics', False)
    kwargs.setdefault('staticdf', None)
    kwargs.setdefault('forcingType','nldas')

    addStatics = kwargs['includeStatics']
    dfStatics = kwargs['staticdf']
    forcingType = kwargs['forcingType']
    latentType = kwargs['latentType']

# Forcing (time series data)

    if addStatics:
        assert(not dfStatics is None)
    if addStatics:
        saved_file = os.path.join(dir_path,f'camels_lstmlist_{forcingType}_{latentType}_seq{seq}_static_new.pkl')
    else:
        saved_file = os.path.join(dir_path,f'camels_lstmlist_{forcingType}_seq{seq}_new.pkl')

    if reGen:
        if genDF:
            allDF=[]
            allQ =[]
            #this loop puts all data in lists
            for basin in basinList:
                print (basin)
                df, area = load_forcing(rootfolder, forcingType, basin=basin)
                dfQ = load_discharge(rootfolder, basin=basin,area=area)
                #forcing var's to use in this project
                colnames = ['PRCP', 'SRAD','Tmax', 'Tmin',    'Vp']
                #subsetting
                df = df[colnames]
                #this makes dfQ index the same as forcing data index
                dfQ = dfQ.reindex(df.index)
                #subsetting on time [use trainstart-seq+1 to be consistent with Krazert]
                df   = df[train_start-pd.Timedelta(seq-1, unit='D'):test_end]
                dfQ = dfQ[train_start-pd.Timedelta(seq-1, unit='D'):test_end]
                #make sure the two dataframes have the same length
                assert(df.shape[0]==dfQ.shape[0])
                allDF.append(df)
                allQ.append(dfQ)
                #for debugging
                """
                if basin in ['05120500']:
                    plt.figure()
                    plt.plot(dfQ[test_start:test_end])
                    plt.savefig('Q{0}.png'.format(basin))
                    plt.close()
                    sys.exit()
                """
            # do normalization
            #get mean correspoinding to training
            inputDF=[]
            outputDF=[]
            #get training data for all basins
            for df1,df2 in zip(allDF,allQ):
                inputDF.append(df1[:train_end])
                outputDF.append(df2[:train_end])
            #calculate stats
            bigDF = pd.concat(inputDF, axis=0)
            bigQDF = pd.concat(outputDF,axis=0)
            bigQMat = bigQDF.to_numpy()
            #do this to remove invalid values in Q
            bigQMat[bigQMat<0.0]=np.NaN
            input_means = np.nanmean(bigDF.to_numpy(), axis=0)
            input_stds = np.nanstd(bigDF.to_numpy(), axis=0)
            output_mean = np.nanmean(bigQMat, axis=0)
            output_std = np.nanstd(bigQMat, axis=0)
            myscaler = {
                'input_means': input_means,
                'input_stds': input_stds,
                'output_mean': output_mean,
                'output_std': output_std,
            }
            print ('training scaler', myscaler)
            bigDF=None
            bigQDF=None
            bigQMat=None
            for ibasin in range(len(allDF)):
                arr = new_normalize_features(allDF[ibasin].to_numpy(),'inputs',myscaler)
                df = pd.DataFrame(arr,index=allDF[ibasin].index)
                df.columns = colnames
                allDF[ibasin]=df

                arr = allQ[ibasin].to_numpy()
                arr[arr<0.0] = np.NaN
                arr = new_normalize_features(arr, 'output',myscaler)
                dfQ = pd.DataFrame(arr,index=allQ[ibasin].index)
                allQ[ibasin] = dfQ
                '''
                test location 05120500
                if ibasin == 288:
                    plt.figure()
                    plt.plot(dfQ[test_start:test_end])
                    plt.savefig(f'Q{ibasin}.png')
                    plt.close()
                    sys.exit()
                '''

            pkl.dump(allDF, open(f'camels_forcingdf_{forcingType}_{latentType}_new.pkl', 'wb'))
            pkl.dump(allQ, open('camels_flow_new.pkl', 'wb'))
            pkl.dump(myscaler, open(f'camels_forcing_scaler_{forcingType}.pkl', 'wb'))

        else:
            allDF=pkl.load(open(f'camels_forcingdf_{forcingType}_{latentType}_new.pkl', 'rb'))
            allQ =pkl.load(open('camels_flow_new.pkl', 'rb'))

        #assumption, the forcing data is contiguous
        nBasins = len(allDF)
        assert(nBasins==len(basinList))

        starttime= default_timer()

        #join all streamflow dataframes
        bigQDF = pd.concat(allQ,axis=1)
        ndays = bigQDF.shape[0]
        trainLen = len(pd.date_range(train_start-pd.Timedelta(seq-1, unit='D'), train_end, freq='D'))
        testLen =  ndays-trainLen
        #the following should be 1096 days
        #print ('test', len(pd.date_range(test_start, test_end, freq='D')))
        print ('all days=', ndays, 'train days ', trainLen, 'test days', testLen)
        print ('finished getting dataframes ...')
        print ('preparing graph data ...')
        """this should print the same figure as the previous Q{ibasin}.png
        plt.figure()
        plt.plot(bigQDF.loc[test_start:test_end].iloc[:,288])
        plt.savefig('big_Q288.png')
        plt.close()
        sys.exit()
        """
# Static Data

        nfeature_d = allDF[0].shape[1]
        nfeatures=nfeature_d
        if addStatics:
            nfeature_s = dfStatics.shape[1] #number of static features
            nfeatures += nfeature_s
        Xtrain_list = []
        ytrain_list = []
        Xtest_list = []
        ytest_list = []

        for irow in range(seq, ndays):
            targetvec = bigQDF.iloc[irow-1,:].to_numpy()

            if not np.isnan(targetvec).any():
                #assuming all data in forcing is continuous
                featureMat = np.zeros((seq,nBasins,nfeatures))
                for ibasin in range(nBasins):
                    featureMat[:,ibasin,:nfeature_d] = allDF[ibasin].iloc[irow-seq:irow,:]
                    if addStatics:
                        featureMat[:,ibasin,nfeature_d:]= dfStatics.iloc[ibasin,:].to_numpy()[np.newaxis,:].repeat(seq,axis=0)

                if irow<trainLen:
                    Xtrain_list.append(featureMat)
                    ytrain_list.append(targetvec)
                else:
                    Xtest_list.append(featureMat)
                    ytest_list.append(targetvec)

        print ("time taken ", default_timer()-starttime)
        print (f'# train: {len(ytrain_list)}, # test: {len(ytest_list)}')

        pkl.dump([Xtrain_list,ytrain_list,Xtest_list,ytest_list], open(saved_file, 'wb'))
    else:
        Xtrain_list,ytrain_list,Xtest_list,ytest_list = pkl.load(open(saved_file, 'rb'))

    return Xtrain_list,ytrain_list,Xtest_list,ytest_list

def genLSTMDataSets(forcingType, latentType, splitratio=(0.8,0.2), seq=60, addStatics=False):
    """Generate LSTM Datasets for training, validation and testing

    Parameters
    ---------
    forcingType: type of forcing datasets
    splitratio: (train,val)
    seq: sequence length
    addStatics: True to include static attributes

    Returns
    --------
    train, validation, and testing datasets
    """

    from torch.utils.data import DataLoader, TensorDataset
    #from torch.utils.data import DataLoader
    import os.path
    dir_path = os.path.dirname(os.path.realpath("__file__"))
    if addStatics:
        #datafile = os.path.join(dir_path, f'camels_lstmlist_{forcingType}_seq{seq}_new.pkl')
        datafile = os.path.join(dir_path, f'camels_lstmlist_{forcingType}_{latentType}_seq{seq}_static_new.pkl')
    else:
        datafile = os.path.join(dir_path, f'camels_lstmlist_{forcingType}_seq{seq}_new.pkl')
    print ('use data from ', datafile)
    Xtrain_list,ytrain_list,Xtest_list,ytest_list = pkl.load(open(datafile, 'rb'))

    nData = len(Xtrain_list)
    nTrain = int(nData*splitratio[0])
    nVal = int(nData*splitratio[1])
    #training
    Xin = toTensor(np.asarray(Xtrain_list[:nTrain]),dtype=torch.float32)
    y  =  toTensor(np.asarray(ytrain_list[:nTrain]),dtype=torch.float32)
    print ('train data', Xin.shape, y.shape)
    trainDataset = TensorDataset(Xin,y)
    #validation
    Xin = toTensor(np.asarray(Xtrain_list[nTrain:]),dtype=torch.float32)
    y  =  toTensor(np.asarray(ytrain_list[nTrain:]),dtype=torch.float32)
    valDataset = TensorDataset(Xin,y)
    print ('val data', Xin.shape, y.shape)
    #testing
    Xin = toTensor(np.asarray(Xtest_list),dtype=torch.float32)
    y  =  toTensor(np.asarray(ytest_list),dtype=torch.float32)
    testDataset = TensorDataset(Xin,y)
    print ('test data', Xin.shape, y.shape)
    nfeatures=Xin.shape[-1]
    return trainDataset,valDataset,testDataset,nfeatures

def loadGraphWeight(filename=None):
    print ('use weight matrix', filename)
    D = scipy.sparse.load_npz(filename)
    return torch_geometric.utils.from_scipy_sparse_matrix(D)

import os

def main():
    #training period and test period
    #based on https://github.com/kratzert/lstm_for_pub/blob/master/main.py
    #i modified the train_end to significantly increase training data sizes
    train_start = pd.to_datetime('01101980', format='%d%m%Y')
    #train_end = pd.to_datetime('30091995', format='%d%m%Y')
    #test_start = pd.to_datetime('01101995', format='%d%m%Y')
    train_end = pd.to_datetime('30092005', format='%d%m%Y')
    test_start = pd.to_datetime('01102005', format='%d%m%Y')
    #test_end = pd.to_datetime('30092008', format='%d%m%Y')
    #as0324, change to camels end date
    test_end = pd.to_datetime('30092014', format='%d%m%Y')

    camelDates = [ train_start, train_end, test_start, test_end]
    dfStaticAll = getStaticAttr()
    df = getSubSet(dfStaticAll)
    #df = getSubSet4Clustering(dfStaticAll)
    rootfolder = Path('C:/Users/cagon/OneDrive/Desktop/Columbia/Camels_Jupyter_Download')
    #
    #
    #for lstm, setting the parameters
    #>>>>>>
    seq=30
    latentdim=8
    addstatics=True
    loadLatent=False
    forcingType='nldas' #nldas, maurer
    if loadLatent:
        latentType=str(latentdim)
    else:
        latentType='full'
    #<<<<<<
    if loadLatent:
        print ("use latent static matrix")
        latentMat = np.load(f'latentMat_dim{latentdim}.npy')
        #normalize the static features
        df = pd.DataFrame(StandardScaler().fit_transform(latentMat),index=df.index)
    else:
        print ('use full static attribute matrix')
        df = pd.DataFrame(StandardScaler().fit_transform(df.to_numpy()),index=df.index)
    print ('static attribute matrix', df.shape)


    kwargs={'includeStatics':addstatics,
            'staticdf':df,
            'latentType':latentType,
            'forcingType': forcingType,
            }

    Xtrain_list,ytrain_list,Xtest_list,ytest_list =  genLSTMData(rootfolder,
            dfStaticAll['gauge_str'],
            seq=seq,
            reGen=True,
            dates=camelDates,
            genDF=True,
            **kwargs
            )

    trainDataset,valDataset,testDataset,_ = genLSTMDataSets(forcingType, latentType, seq=seq,addStatics=addstatics)

if __name__ == '__main__':
    main()

#main("--seq 30 --addstatics --forcingtype nldas")