export type RootState = ReturnType<typeof import('./store').store.getState>;
export type AppDispatch = typeof import('./store').store.dispatch;
export type AppThunk<ReturnType = void> = import('@reduxjs/toolkit').ThunkAction<
    ReturnType,
    RootState,
    unknown,
    import('@reduxjs/toolkit').Action<string>
>;
