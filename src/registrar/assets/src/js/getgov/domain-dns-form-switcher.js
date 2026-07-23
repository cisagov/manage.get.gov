class DNSFormSwitcher{
    /**
     * Manages DNS form switching from Alpine Data
     * Requires an HTML container with Alpine.js initialized on it
     * 
     * State:
     * - pending: an object { type, recordId} representing the form the user is currently on
     *   type is either "edit" or "add", recordID is the form's recordID
     * - target: the form  ID the user is clicking to.
     * 
     * Methods
     * - getAlpineData: returns the Alpine data object for the container
     * - resetPendingAndTarget: resets the target, and pending values to null
     *
    */ 
   
    constructor(container){
        this.pending = null;
        this.target = null;
        this.container = container;
    }

    setPending(value) {
         this.pending = value;
    }


    getAlpineData(){
        return Alpine.$data(this.container);
    }


    resetPendingAndTarget(){
       this.setTarget(null);
       this.setPending(null);
    }

}

export class EditFormSwitcher extends DNSFormSwitcher{
    /**
     * EditFormSwitcher for changes between edit forms, and opening the add record
     * State: inherited from DNSFormSwitcher
     * showFormId: the form number that is set on showFormId on Alpine data will show on the UI
     * - the value 0 represents that the add Record form is open
     * - values above 0 represents the edit forms in the table rows
     * Methods:
     * - setTarget: toggle from closing and opening the form if same value, and if different value set the form target;
     * - setShowFormId: update the showFormId in Alpine data
     * - getCurrentShowFormId: get current showFormId from Alpine data
     * - attemptOpen: sets the pending target in a dict to be used in the refsForm method to get the focusId, buttonId, and form
     * - switchForm: uses setShowFormId to switch showFormId to current target, and reset the target and pending values
     * - createReq: creates the dict for the refForm method in the domain-dns-record-content.js
     */

    setTarget(value){  
        const current = this.getCurrentShowFormId();
        this.target = current == value ? null : value;
    }

    setShowId(value){
        const data = this.getAlpineData();
        data.showFormId = value;
    }
   
    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }

    getCurrentShowFormId(){
        return this.getAlpineData().showFormId
    }

    createReq(currentId){
      return {
            type: currentId > 0 ? "edit" : "add",
            recordId: currentId
        }
    }
   
    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getCurrentShowFormId();
        this.setPending(this.createReq(currentId));
    }

    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }
}

export class RecordSelectTypeSwitcher extends DNSFormSwitcher{
    /**
     * RecordSelectTypeSwitcher for changes between the add record types
     * State: inherited from DNSFormSwitcher, and isRecordType is differentiate between this and the EditFormSwitcher
     * Method:
     * - createReq: creates the dict for the refForm method in the domain-dns-record-content.js
     * - setRecordType: sets recordType on the Alpine data obj
     * - attemptOpen: sets the current element to the pending value
     * - updatedSelectedType: switches the value in the select element to the current target value if none is given
     * - switchForm: updates recordType in Alpine data, update the select html element to the target, and resets the target and pending
     */

    constructor(container){
        super(container);
        this.isRecordType = true;
    }

    createReq(currentId){
       return {
            type: 'add',
            recordId: currentId,
            isRecordType: this.isRecordType
        }
    }

    setTarget(value){
        this.target = value;
    }

    setRecordType(value = this.target){
        const data = this.getAlpineData();
        data.recordType = value;
    }

    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getAlpineData().recordType;
        this.setPending(this.createReq(currentId));
    }

    updateSelectedType(value = this.target){ 
        const selectEl= this.container.querySelector("#id_type")
        selectEl.selectedIndex = value;
        // programmatically dispatches change event for alpine to switch the form, and to get the appropiate form labels
        const changeEvent = new Event('change');
        selectEl.querySelector("#id_type").dispatchEvent(changeEvent);
    }

    switchForm(value = this.target){
       this.setRecordType(value);
       this.updateSelectedType(value);  
       this.resetPendingAndTarget();
    }
}