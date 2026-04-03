package com.gamevil.lib;

import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;

public class GvActivity extends AppCompatActivity {
    protected static GvActivity myActivity;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        myActivity = this;
    }

    public void onGameResume() {
        // Hook point mirrored from the legacy stack.
    }
}

